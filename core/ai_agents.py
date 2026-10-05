import logging
from functools import lru_cache
from pathlib import Path

import ollama
from django.conf import settings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from core.ai_router import analyze_stock
logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# CHROMA DATABASE
# ---------------------------------------------------------

DB_DIR = Path(settings.BASE_DIR) / "chroma_db"


def _get_chroma_directory():
    """
    Return the project-local Chroma directory.
    The path is always based on Django BASE_DIR,
    not the current terminal working directory.
    """

    if DB_DIR.exists() and not DB_DIR.is_dir():
        raise RuntimeError(
            f"Chroma path is not a directory: {DB_DIR}"
        )

    DB_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    return DB_DIR


@lru_cache(maxsize=1)
def get_vector_store():
    """
    Load the embedding model and Chroma vector store
    only once per Django process.
    """

    persist_directory = _get_chroma_directory()

    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    return Chroma(
        persist_directory=str(persist_directory),
        embedding_function=embedding_model
    )


# ---------------------------------------------------------
# OMNI QUANT AI SPECIALIST
# ---------------------------------------------------------

class OmniQuantSpecialist:

    SPECIALIST_RULES = {

        "STOCKS":
            "Focus on momentum, volume gaps, and technical breakouts.",

        "FOREX":
            "Focus on macro-liquidity and base currency strength.",

        "CRYPTO":
            "Analyze extreme volatility and on-chain sentiment.",

        "COMMODITY":
            "Evaluate supply-demand shifts and future pricing.",

        "OPTIONS":
            "Analyze implied volatility and premium decay.",

        "BONDS":
            "Analyze yield curve shifts, central bank interest rate expectations, and macro-economic debt indicators."
    }

    # -----------------------------------------------------
    # MAIN INTELLIGENCE ENGINE
    # -----------------------------------------------------

    @classmethod
    def generate_intelligence(
        cls,
        segment,
        symbol,
        price_data,
        news_data,
        ear_score=None
    ):

        # -------------------------------------------------
        # 1. MARKET DATA VALIDATION
        # -------------------------------------------------

        if not price_data:

            return {
                "status": "ERROR",
                "insight":
                    "> ERROR: No market data received."
            }

        if len(price_data) < 2:

            return {
                "status": "ERROR",
                "insight":
                    "> ERROR: Insufficient market data."
            }

        # -------------------------------------------------
        # 2. SAFELY READ PRICES
        # -------------------------------------------------

        try:

            current_price = float(
                price_data[-1]["close"]
            )

            start_price = float(
                price_data[0]["close"]
            )

        except (
            KeyError,
            TypeError,
            ValueError
        ):

            logger.exception(
                "Invalid price data for %s",
                symbol
            )

            return {
                "status": "ERROR",
                "insight":
                    "> ERROR: Invalid market price data."
            }

        # -------------------------------------------------
        # 3. PREVENT DIVISION BY ZERO
        # -------------------------------------------------

        if start_price == 0:

            logger.error(
                "Starting price is zero for %s",
                symbol
            )

            return {
                "status": "ERROR",
                "insight":
                    "> ERROR: Invalid market data. Starting price is zero."
            }

        if current_price <= 0:

            return {
                "status": "ERROR",
                "insight":
                    "> ERROR: Invalid current market price."
            }

        # -------------------------------------------------
        # 4. CALCULATE PRICE CHANGE
        # -------------------------------------------------

        percent_change = (
            (
                current_price -
                start_price
            )
            /
            start_price
        ) * 100

        # -------------------------------------------------
        # 5. DETERMINE TREND
        # -------------------------------------------------

        if percent_change > 0:

            trend = "BULLISH"

        elif percent_change < 0:

            trend = "BEARISH"

        else:

            trend = "NEUTRAL"

        # -------------------------------------------------
        # 6. MARKET DATA CONTEXT
        # -------------------------------------------------

        data_context = (
            f"Current Price: {current_price:.4f} | "
            f"Starting Price: {start_price:.4f} | "
            f"Trend: {trend} "
            f"({percent_change:.2f}%)"
        )

        # -------------------------------------------------
        # 7. NEWS CONTEXT
        # -------------------------------------------------

        if news_data:

            titles = []

            for news_item in news_data[:3]:

                title = news_item.get(
                    "title"
                )

                if title:

                    titles.append(
                        str(title)
                    )

            news_context = (
                " | ".join(titles)
                if titles
                else
                "No live news."
            )

        else:

            news_context = "No live news."

        # -------------------------------------------------
        # 8. SPECIALIST RULE
        # -------------------------------------------------

        rule = cls.SPECIALIST_RULES.get(
            segment,
            "Maintain neutral stance."
        )

        # -------------------------------------------------
        # 9. CHROMA KNOWLEDGE VAULT
        # -------------------------------------------------

        vault_context = (
            "Vault unavailable; "
            "continuing without stored intelligence."
        )

        try:

            search_query = (
                f"{segment} trading strategy "
                f"for a {trend} market."
            )

            vector_db = get_vector_store()

            retrieved_docs = (
                vector_db.similarity_search(
                    search_query,
                    k=1
                )
            )

            if retrieved_docs:

                page_content = (
                    retrieved_docs[0]
                    .page_content
                )

                if page_content:

                    vault_context = (
                        page_content[:400]
                    )

        except Exception as error:

            logger.exception(
                "Chroma knowledge-vault retrieval failed: %s",
                error
            )

        # -------------------------------------------------
        # 10. PROMPT
        # -------------------------------------------------

        prompt = f"""
System: You are OmniQuant Bio-Sentinel, a highly precise quantitative trading AI.

[DATA FEED]

Asset:
{symbol}

Segment:
{segment}

Market Data:
{data_context}

News:
{news_context}

Vault Strategy:
{vault_context}

Segment Rule:
{rule}

[INSTRUCTIONS]

Analyze the supplied market data.

Calculate a confidence score from 0 to 100.

Output EXACTLY this format:

SIGNAL: <BUY, SELL, or WAIT> | CONFIDENCE: <0-100>% | CLEARANCE: <OPTIMAL, CAUTION, or HOLD>
> REASON: <ONE technical sentence>

Do not use markdown.
Do not use bullet points.
Do not write conversational text.
"""

        # -------------------------------------------------
        # 11. OLLAMA
        # -------------------------------------------------

        try:

            response = ollama.chat(

                model="llama3.2",

                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Safely extract Ollama response
            message = response.get(
                "message",
                {}
            )

            content = message.get(
                "content",
                ""
            )

            if not content:

                return {
                    "status": "ERROR",
                    "insight":
                        "> ERROR: Ollama returned an empty response."
                }

            return {

                "status": "STABLE",

                "insight":
                    content.strip()
            }

        except Exception as error:

            logger.exception(
                "Ollama intelligence generation failed: %s",
                error
            )

            return {

                "status":
                    "OFFLINE",

                "insight":
                    (
                        "> ERROR: Local AI Engine offline. "
                        f"({error})"
                    )
            }