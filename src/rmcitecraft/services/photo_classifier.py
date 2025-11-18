"""
Photo classification service for Find a Grave images.

Classifies untagged photos into categories:
- Person (portrait or individual photo)
- Grave (headstone, marker, or gravesite)
- Family (group photo with multiple people)
- Document (certificate, record, or paper document)
- Cemetery (wider cemetery view)
- Other (anything else)
"""

import os
from pathlib import Path
from typing import Optional

from loguru import logger

from rmcitecraft.llm import create_provider, LLMProvider, ClassificationResponse


class PhotoClassifier:
    """Service for classifying Find a Grave photos."""

    # Standard Find a Grave photo categories
    CATEGORIES = [
        "Person",      # Individual portrait/photo
        "Grave",       # Headstone or grave marker
        "Family",      # Group photo
        "Document",    # Certificate, record, paper
        "Cemetery",    # Wide cemetery view
        "Flowers",     # Memorial flowers
        "Other",       # Anything else
    ]

    def __init__(self, provider: Optional[LLMProvider] = None,
                 model: Optional[str] = None):
        """
        Initialize photo classifier.

        Args:
            provider: LLM provider to use (or create from config)
            model: Model to use for classification
        """
        if provider:
            self.provider = provider
        else:
            # Create from environment config
            config = self._load_config()
            self.provider = create_provider(config)

        # Use configured model or provider default
        self.model = model or os.getenv("PHOTO_CLASSIFICATION_MODEL")

        logger.info(f"Photo classifier initialized with {self.provider.name}")
        if self.model:
            logger.info(f"Using model: {self.model}")

    def _load_config(self) -> dict:
        """Load configuration from environment."""
        provider_type = os.getenv("DEFAULT_LLM_PROVIDER", "openrouter")

        config = {
            "provider": provider_type,
        }

        # Add provider-specific config
        if provider_type == "openrouter":
            config["openrouter_api_key"] = os.getenv("OPENROUTER_API_KEY")
            config["openrouter_site_url"] = os.getenv("OPENROUTER_SITE_URL")
            config["openrouter_app_name"] = os.getenv("OPENROUTER_APP_NAME", "RMCitecraft")

        return config

    def classify_photo(self, image_path: str | Path) -> ClassificationResponse:
        """
        Classify a Find a Grave photo.

        Args:
            image_path: Path to the image file

        Returns:
            ClassificationResponse with category and confidence

        Raises:
            FileNotFoundError: If image doesn't exist
            LLMError: If classification fails
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        logger.info(f"Classifying photo: {image_path.name}")

        # Use provider's classify_image method
        try:
            response = self.provider.classify_image(
                str(image_path),
                self.CATEGORIES,
                model=self.model
            )

            logger.info(
                f"Classified as '{response.category}' "
                f"with confidence {response.confidence:.2%}"
            )

            return response

        except NotImplementedError:
            # Provider doesn't support image classification
            # Fall back to manual prompt
            logger.warning(
                f"{self.provider.name} doesn't have native image classification. "
                "Using manual prompt."
            )
            return self._classify_with_prompt(image_path)

    def _classify_with_prompt(self, image_path: Path) -> ClassificationResponse:
        """
        Classify using manual prompt (fallback method).

        Args:
            image_path: Path to the image file

        Returns:
            ClassificationResponse
        """
        prompt = f"""You are classifying a photo from Find a Grave memorial website.

Classify this image into exactly ONE of these categories:
- Person: Individual portrait or photo of a single person
- Grave: Headstone, grave marker, or tombstone
- Family: Group photo with multiple people
- Document: Certificate, record, newspaper clipping, or paper document
- Cemetery: Wide view of cemetery grounds or multiple graves
- Flowers: Memorial flowers or floral arrangements
- Other: Anything that doesn't fit the above categories

Respond in JSON format:
{{
    "category": "chosen category from the list above",
    "confidence": 0.95,
    "reasoning": "brief explanation of why you chose this category"
}}

Be accurate - this will be used to organize photos in a genealogy database."""

        response = self.provider.complete_with_image(
            prompt,
            str(image_path),
            model=self.model,
            temperature=0.3  # Low temperature for consistency
        )

        # Parse response
        import json
        try:
            data = json.loads(response.text)

            # Validate category
            category = data.get("category", "Other")
            if category not in self.CATEGORIES:
                logger.warning(f"Invalid category '{category}', defaulting to 'Other'")
                category = "Other"

            return ClassificationResponse(
                category=category,
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning"),
                metadata={"raw_response": response.text}
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse classification response: {e}")
            # Default to "Other" with low confidence
            return ClassificationResponse(
                category="Other",
                confidence=0.3,
                reasoning="Failed to parse LLM response",
                metadata={"error": str(e), "raw_response": response.text}
            )

    def classify_batch(self, image_paths: list[str | Path],
                      progress_callback=None) -> dict[str, ClassificationResponse]:
        """
        Classify multiple photos.

        Args:
            image_paths: List of image paths
            progress_callback: Optional callback(current, total, path)

        Returns:
            Dict mapping image path to ClassificationResponse
        """
        results = {}
        total = len(image_paths)

        for i, image_path in enumerate(image_paths, 1):
            if progress_callback:
                progress_callback(i, total, image_path)

            try:
                result = self.classify_photo(image_path)
                results[str(image_path)] = result
            except Exception as e:
                logger.error(f"Failed to classify {image_path}: {e}")
                # Store error result
                results[str(image_path)] = ClassificationResponse(
                    category="Other",
                    confidence=0.0,
                    reasoning=f"Classification failed: {e}"
                )

        return results

    def suggest_photo_type(self, description: str) -> str:
        """
        Suggest photo type based on text description.

        Useful when Find a Grave provides a description but no type.

        Args:
            description: Photo description text

        Returns:
            Suggested category
        """
        if not description:
            return "Other"

        description_lower = description.lower()

        # Keywords for each category
        person_keywords = ["portrait", "person", "individual", "man", "woman",
                          "boy", "girl", "child", "baby"]
        grave_keywords = ["headstone", "grave", "marker", "tombstone", "stone",
                         "monument", "memorial", "inscription"]
        family_keywords = ["family", "group", "children", "parents", "siblings",
                          "couple", "wedding"]
        document_keywords = ["certificate", "record", "document", "paper",
                            "newspaper", "obit", "death cert", "birth cert"]
        cemetery_keywords = ["cemetery", "graveyard", "grounds", "overview",
                            "entrance", "gate"]
        flower_keywords = ["flowers", "bouquet", "wreath", "roses", "floral"]

        # Check keywords
        for keyword in grave_keywords:
            if keyword in description_lower:
                return "Grave"

        for keyword in person_keywords:
            if keyword in description_lower:
                return "Person"

        for keyword in family_keywords:
            if keyword in description_lower:
                return "Family"

        for keyword in document_keywords:
            if keyword in description_lower:
                return "Document"

        for keyword in cemetery_keywords:
            if keyword in description_lower:
                return "Cemetery"

        for keyword in flower_keywords:
            if keyword in description_lower:
                return "Flowers"

        return "Other"