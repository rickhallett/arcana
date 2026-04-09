from langgraph.graph import END, StateGraph

from arcana.orchestrator.nats_dispatch import DispatchError, NATSDispatcher
from arcana.orchestrator.state import QueryState


def build_query_graph(dispatcher: NATSDispatcher, vector_store):
    async def retrieve_node(state: QueryState) -> QueryState:
        results = vector_store.query(state["question"], n_results=10)
        if not results["ids"]:
            return {
                **state,
                "chunks": [],
                "chunk_ids": [],
                "distances": [],
                "status": "no_results",
            }
        return {
            **state,
            "chunks": results["documents"],
            "chunk_ids": results["ids"],
            "distances": results["distances"],
            "status": "retrieved",
        }

    def should_analyse(state: QueryState) -> str:
        return "synthesise" if state.get("status") == "no_results" else "analyse"

    async def analyse_node(state: QueryState) -> QueryState:
        try:
            result = await dispatcher.dispatch(
                subject="arcana.analyse",
                payload={
                    "job_id": state["job_id"],
                    "question": state["question"],
                    "chunks": state["chunks"],
                    "chunk_ids": state["chunk_ids"],
                },
                job_id=state["job_id"],
                step="analyse",
                correlation_id=state["job_id"],
            )
            return {
                **state,
                "draft": result["draft"],
                "citations": result["citations"],
                "status": "analysed",
            }
        except DispatchError as e:
            return {**state, "status": "failed", "error": str(e)}

    async def check_node(state: QueryState) -> QueryState:
        try:
            result = await dispatcher.dispatch(
                subject="arcana.check",
                payload={
                    "job_id": state["job_id"],
                    "draft": state["draft"],
                    "chunks": state["chunks"],
                    "chunk_ids": state["chunk_ids"],
                },
                job_id=state["job_id"],
                step="check",
                correlation_id=state["job_id"],
            )
            return {**state, "claims": result["claims"], "status": "checked"}
        except DispatchError as e:
            return {**state, "status": "failed", "error": str(e)}

    async def synthesise_node(state: QueryState) -> QueryState:
        if state.get("status") == "no_results":
            return {
                **state,
                "answer": "No relevant documents found for this question.",
                "claims": [],
                "confidence": 0.0,
                "cost_usd": 0.0,
                "duration_s": 0.0,
                "status": "completed",
            }
        claims = state.get("claims", [])
        supported = sum(1 for c in claims if c.get("verdict") == "supported")
        total = len(claims) if claims else 1
        confidence = supported / total
        return {
            **state,
            "answer": state.get("draft", ""),
            "confidence": round(confidence, 2),
            "status": "completed",
        }

    def should_continue_after(target):
        def check(state: QueryState) -> str:
            return END if state.get("status") == "failed" else target
        return check

    graph = StateGraph(QueryState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("analyse", analyse_node)
    graph.add_node("check", check_node)
    graph.add_node("synthesise", synthesise_node)
    graph.set_entry_point("retrieve")
    graph.add_conditional_edges(
        "retrieve", should_analyse, {"analyse": "analyse", "synthesise": "synthesise"}
    )
    graph.add_conditional_edges(
        "analyse", should_continue_after("check"), {"check": "check", END: END}
    )
    graph.add_conditional_edges(
        "check", should_continue_after("synthesise"), {"synthesise": "synthesise", END: END}
    )
    graph.add_edge("synthesise", END)
    return graph.compile()
