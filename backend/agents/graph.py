from functools import partial
from langgraph.graph import StateGraph
from langgraph.constants import END
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.state import InvoiceState
from backend.agents.ingestion_agent import IngestionAgent
from backend.agents.validation_agent import ValidationAgent
from backend.agents.anomaly_agent import AnomalyAgent
from backend.core.logging import logger


# ── Agent instances ───────────────────────────────────────────────────────────
ingestion_agent = IngestionAgent()
validation_agent = ValidationAgent()
anomaly_agent = AnomalyAgent()


# ── Node functions ────────────────────────────────────────────────────────────

async def run_ingestion(state: InvoiceState, db: AsyncSession) -> InvoiceState:
    """Node 1 — Ingestion Agent"""
    logger.info("graph.node", node="ingestion")
    try:
        invoice = await ingestion_agent.process(
            db=db,
            file_bytes=state.get("file_bytes"),
            filename=state.get("filename", ""),
            raw_text=state.get("raw_text"),
        )

        state["invoice_id"] = str(invoice.id)
        state["vendor_name"] = invoice.vendor_name
        state["invoice_number"] = invoice.invoice_number
        state["amount"] = invoice.amount
        state["currency"] = invoice.currency
        state["ingestion_complete"] = True
        state["current_agent"] = "ingestion"
        state["reasoning"].append(
            f"Ingestion: extracted vendor={invoice.vendor_name}, "
            f"amount={invoice.amount} {invoice.currency}"
        )

    except Exception as e:
        state["error"] = str(e)
        state["ingestion_complete"] = False
        state["requires_human_review"] = True
        logger.error("graph.ingestion_failed", error=str(e))

    return state


async def run_validation(state: InvoiceState, db: AsyncSession) -> InvoiceState:
    """Node 2 — Validation Agent"""
    logger.info("graph.node", node="validation")
    try:
        from backend.db.models.invoice import Invoice
        from sqlalchemy import select

        result = await db.execute(
            select(Invoice).where(Invoice.id == state["invoice_id"])
        )
        invoice = result.scalar_one_or_none()

        if not invoice:
            raise ValueError(f"Invoice {state['invoice_id']} not found")

        validation_result = await validation_agent.process(
            db=db,
            invoice=invoice
        )

        state["is_valid"] = validation_result.is_valid
        state["validation_flags"] = validation_result.flags
        state["validation_complete"] = True
        state["current_agent"] = "validation"
        state["reasoning"].append(
            f"Validation: is_valid={validation_result.is_valid}, "
            f"flags={validation_result.flags}"
        )

        if not validation_result.is_valid:
            state["requires_human_review"] = True

    except Exception as e:
        state["error"] = str(e)
        state["validation_complete"] = False
        state["requires_human_review"] = True
        logger.error("graph.validation_failed", error=str(e))

    return state


async def run_anomaly(state: InvoiceState, db: AsyncSession) -> InvoiceState:
    """Node 3 — Anomaly Agent (real implementation)"""
    logger.info("graph.node", node="anomaly")
    try:
        from backend.db.models.invoice import Invoice
        from sqlalchemy import select

        result = await db.execute(
            select(Invoice).where(Invoice.id == state["invoice_id"])
        )
        invoice = result.scalar_one_or_none()

        if not invoice:
            raise ValueError(f"Invoice {state['invoice_id']} not found")

        flags = await anomaly_agent.process(db=db, invoice=invoice)

        state["anomaly_flags"] = flags
        state["is_anomalous"] = len(flags) > 0
        state["anomaly_complete"] = True
        state["current_agent"] = "anomaly"
        state["reasoning"].append(
            f"Anomaly: score={invoice.anomaly_score:.2f}, "
            f"flags={flags if flags else 'none'}"
        )

        if state["is_anomalous"]:
            state["requires_human_review"] = True

    except Exception as e:
        state["error"] = str(e)
        state["anomaly_complete"] = False
        logger.error("graph.anomaly_failed", error=str(e))

    return state


async def run_human_queue(state: InvoiceState, db: AsyncSession) -> InvoiceState:
    """Node 4 — Human Review Queue"""
    logger.info("graph.node", node="human_queue",
                invoice_id=state.get("invoice_id"))

    state["requires_human_review"] = True
    state["current_agent"] = "human_queue"
    state["reasoning"].append(
        f"Human review required. "
        f"Validation flags: {state.get('validation_flags', [])}. "
        f"Anomaly flags: {state.get('anomaly_flags', [])}"
    )

    return state


# ── Routing functions ─────────────────────────────────────────────────────────

def route_after_ingestion(state: InvoiceState) -> str:
    if state.get("error") or not state.get("ingestion_complete"):
        return "human_queue"
    return "validation"


def route_after_validation(state: InvoiceState) -> str:
    if not state.get("is_valid"):
        return "human_queue"
    return "anomaly"


def route_after_anomaly(state: InvoiceState) -> str:
    if state.get("is_anomalous"):
        return "human_queue"
    return END


# ── Build the graph ───────────────────────────────────────────────────────────

def create_invoice_graph(db: AsyncSession):
    graph = StateGraph(InvoiceState)

    graph.add_node("ingestion", partial(run_ingestion, db=db))
    graph.add_node("validation", partial(run_validation, db=db))
    graph.add_node("anomaly", partial(run_anomaly, db=db))
    graph.add_node("human_queue", partial(run_human_queue, db=db))

    graph.set_entry_point("ingestion")

    graph.add_conditional_edges("ingestion", route_after_ingestion)
    graph.add_conditional_edges("validation", route_after_validation)
    graph.add_conditional_edges("anomaly", route_after_anomaly)

    graph.add_edge("human_queue", END)

    return graph.compile()


# ── Main entry point ──────────────────────────────────────────────────────────

async def process_invoice_graph(
    db: AsyncSession,
    file_bytes: bytes = None,
    filename: str = "",
    raw_text: str = None,
) -> InvoiceState:
    initial_state: InvoiceState = {
        "invoice_id": None,
        "file_bytes": file_bytes,
        "filename": filename,
        "raw_text": raw_text,
        "vendor_name": None,
        "invoice_number": None,
        "amount": None,
        "currency": None,
        "ingestion_complete": False,
        "validation_complete": False,
        "anomaly_complete": False,
        "is_valid": False,
        "is_anomalous": False,
        "requires_human_review": False,
        "validation_flags": [],
        "anomaly_flags": [],
        "reasoning": [],
        "error": None,
        "current_agent": None,
    }

    graph = create_invoice_graph(db)
    final_state = await graph.ainvoke(initial_state)

    logger.info(
        "graph.completed",
        invoice_id=final_state.get("invoice_id"),
        is_valid=final_state.get("is_valid"),
        is_anomalous=final_state.get("is_anomalous"),
        requires_human_review=final_state.get("requires_human_review"),
        reasoning=final_state.get("reasoning"),
    )

    return final_state