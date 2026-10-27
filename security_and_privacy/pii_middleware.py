
import re
import logging

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider

logger = logging.getLogger(__name__)


# --------------------------------------------------
# PRESIDIO CONFIGURATION
# --------------------------------------------------

configuration = {
    "nlp_engine_name": "spacy",
    "models": [
        {
            "lang_code": "en",
            "model_name": "en_core_web_sm",
        }
    ],
}

provider = NlpEngineProvider(
    nlp_configuration=configuration
)

nlp_engine = provider.create_engine()

analyzer = AnalyzerEngine(
    nlp_engine=nlp_engine,
    supported_languages=["en"],
)


# --------------------------------------------------
# REUSABLE PII SESSION
# --------------------------------------------------

class PIISanitizer:

    def __init__(self):

        self.original_to_token = {}
        self.token_to_original = {}

        self.entity_counters = {}

    def sanitize(self, text: str) -> str:

        if not text:
            return text

        results = analyzer.analyze(
            text=text,
            language="en",
        )

        # Process detected entities in text order.
        results.sort(
            key=lambda item: (
                item.start,
                -(item.end - item.start),
            )
        )

        replacements = []
        last_end = 0

        for result in results:

            start = result.start
            end = result.end

            # Ignore overlapping detections.
            if start < last_end:
                continue

            original_value = text[start:end]

            entity_type = result.entity_type

            key = (
                entity_type,
                original_value,
            )

            # Reuse the same placeholder for repeated values.
            if key not in self.original_to_token:

                count = (
                    self.entity_counters.get(
                        entity_type, 0
                    ) + 1
                )

                self.entity_counters[entity_type] = count

                token = f"[{entity_type}_{count}]"

                self.original_to_token[key] = token

                self.token_to_original[token] = original_value

            else:

                token = self.original_to_token[key]

            replacements.append(
                (start, end, token)
            )

            last_end = end

        # Build sanitized text.
        output = []
        last_position = 0

        for start, end, token in replacements:

            output.append(
                text[last_position:start]
            )

            output.append(token)

            last_position = end

        output.append(text[last_position:])

        sanitized_text = "".join(output)

        return sanitized_text

    # --------------------------------------------------
    # RESTORE ORIGINAL PII
    # --------------------------------------------------

    def restore(self, text: str) -> str:

        if not text or not self.token_to_original:
            return text

        pattern = re.compile(
            "|".join(
                re.escape(token)
                for token in sorted(
                    self.token_to_original,
                    key=len,
                    reverse=True,
                )
            )
        )

        return pattern.sub(
            lambda match: self.token_to_original[
                match.group(0)
            ],
            text,
        )
