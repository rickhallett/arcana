from langgraph.graph import END, StateGraph

from arcana.orchestrator.nats_dispatch import DispatchError, NATSDispatcher
from arcana.orchestrator.state import IngestState


def build_ingest_graph(dispatcher: NATSDispatcher):
    async def extract_node(state: IngestState) -> IngestState:
        try:
            result = await dispatcher.dispatch(
                subject="arcana.extract",
                payload={
                    "job_id": state["job_id"],
                    "file_path": state["file_path"],
                    "file_checksum": state["file_checksum"],
                    "doc_type": state["doc_type"],
                },
                job_id=state["job_id"],
                step="extract",
                correlation_id=state["job_id"],
            )
            return {
                **state,
                "text": result["text"],
                "title": result["title"],
                "pages": result["pages"],
                "status": "extracting",
            }
        except DispatchError as e:
            return {**state, "status": "failed", "error": str(e)}

    async def embed_node(state: IngestState) -> IngestState:
        try:
            result = await dispatcher.dispatch(
                subject="arcana.embed",
                payload={
                    "job_id": state["job_id"],
                    "text": state["text"],
                    "title": state["title"],
                    "doc_type": state["doc_type"],
                },
                job_id=state["job_id"],
                step="embed",
                correlation_id=state["job_id"],
            )
            return {
                **state,
                "chunk_count": result["chunk_count"],
                "collection": result["collection"],
                "status": "completed",
            }
        except DispatchError as e:
            return {**state, "status": "failed", "error": str(e)}

    def should_continue(state: IngestState) -> str:
        if state.get("status") == "failed":
            return END
        return "embed"

    graph = StateGraph(IngestState)
    graph.add_node("extract", extract_node)
    graph.add_node("embed", embed_node)
    graph.set_entry_point("extract")
    graph.add_conditional_edges(
        "extract", should_continue, {"embed": "embed", END: END}
    )
    graph.add_edge("embed", END)
    return graph.compile()
