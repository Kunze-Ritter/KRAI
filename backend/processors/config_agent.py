"""
AI Agent for Product Configuration Questions

Answers questions like:
- "Can I use MK-746 with C4080?"
- "What accessories do I need for SD-513?"
- "Is this configuration valid: C4080 + MK-746 + SD-506?"
"""

import json

from config_validator import CompatibilityType, ConfigurationValidator


class ConfigurationAgent:
    """
    AI Agent that answers configuration questions

    Example:
        agent = ConfigurationAgent()
        agent.load_from_json("products_compatibility.json")

        answer = agent.ask("Can I use MK-746 with C4080?")
        print(answer)
    """

    def __init__(self):
        """Initialize agent"""
        self.validator = ConfigurationValidator()
        self.loaded = False

    def load_from_json(self, filepath: str):
        """
        Load product and compatibility data from JSON

        JSON format:
        {
          "products": [
            {"model_number": "C4080", "product_type": "printer"},
            ...
          ],
          "relationships": [
            {
              "product_1": "C4080",
              "product_2": "MK-746",
              "type": "compatible",
              "notes": "Finisher works with printer"
            },
            ...
          ]
        }
        """
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        # Load products
        for product in data.get("products", []):
            self.validator.add_product(
                model_number=product["model_number"],
                product_type=product.get("product_type", "unknown"),
                specifications=product.get("specifications"),
            )

        # Load relationships
        for rel in data.get("relationships", []):
            self.validator.add_relationship(
                product_1=rel["product_1"],
                product_2=rel["product_2"],
                relationship_type=CompatibilityType(rel["type"]),
                notes=rel.get("notes"),
                priority=rel.get("priority", 0),
            )

        self.loaded = True

    def load_from_database(self, connection):
        """
        Load from Supabase database

        Queries:
        - SELECT * FROM krai_core.products
        - SELECT * FROM krai_core.product_accessories
        """
        # Query products
        products_result = connection.table("vw_products").select("*").execute()
        for product in products_result.data:
            self.validator.add_product(
                model_number=product["model_number"],
                product_type=product["product_type"],
                specifications=product.get("specifications"),
            )

        # Query relationships
        rels_result = connection.table("product_accessories").select("*").execute()
        for rel in rels_result.data:
            # Get model numbers from IDs
            p1 = next((p for p in products_result.data if p["id"] == rel["product_id"]), None)
            p2 = next((p for p in products_result.data if p["id"] == rel["accessory_id"]), None)

            if p1 and p2:
                self.validator.add_relationship(
                    product_1=p1["model_number"],
                    product_2=p2["model_number"],
                    relationship_type=CompatibilityType(rel["compatibility_type"]),
                    notes=rel.get("compatibility_notes"),
                    priority=rel.get("priority", 0),
                )

        self.loaded = True

    def ask(self, question: str) -> str:
        """
        Answer a natural language question about product configuration

        Supported question types:
        - "Can I use X with Y?"
        - "What do I need for X?"
        - "Is X compatible with Y?"
        - "Does X conflict with Y?"
        - "Validate: X + Y + Z"
        """
        question_lower = question.lower().strip()

        # Extract product models from question
        products = self._extract_products(question)

        if not products:
            return "❌ No products found in question. Please mention model numbers (e.g., C4080, MK-746)."

        # Question type: Compatibility check (2 products)
        if ("can i use" in question_lower or "compatible" in question_lower) and len(products) == 2:
            return self._answer_compatibility(products[0], products[1])

        # Question type: Requirements
        if ("what" in question_lower and "need" in question_lower) and len(products) == 1:
            return self._answer_requirements(products[0])

        # Question type: Conflict check
        if "conflict" in question_lower and len(products) == 2:
            return self._answer_conflict(products[0], products[1])

        # Question type: Configuration validation
        if "validate" in question_lower or "+" in question:
            if len(products) < 2:
                return "❌ Please specify a base product and at least one accessory."
            return self._answer_validate_config(products[0], products[1:])

        # Question type: Recommendations
        if "recommend" in question_lower and len(products) == 1:
            return self._answer_recommendations(products[0])

        # Default: Show what we know about the products
        return self._answer_general(products)

    def _extract_products(self, text: str) -> list[str]:
        """Extract product model numbers from text"""
        # Simple extraction: find all registered products in text
        found = []
        text_upper = text.upper()
        for model in self.validator.products:
            if model.upper() in text_upper:
                found.append(model)
        return found

    def _answer_compatibility(self, product_1: str, product_2: str) -> str:
        """Answer: Can I use X with Y?"""
        compatible, reason = self.validator.check_compatibility(product_1, product_2)

        if compatible:
            # Check if there are requirements
            req_1 = self.validator.get_required_accessories(product_1)
            req_2 = self.validator.get_required_accessories(product_2)

            response = f"✅ **Yes, {product_1} is compatible with {product_2}**\n\n"

            if req_1:
                response += f"📋 Note: {product_1} requires: {', '.join(req_1)}\n"
            if req_2:
                response += f"📋 Note: {product_2} requires: {', '.join(req_2)}\n"

            return response.strip()
        return f"❌ **No, {product_1} is NOT compatible with {product_2}**\n\n" f"Reason: {reason}"

    def _answer_requirements(self, product: str) -> str:
        """Answer: What do I need for X?"""
        required = self.validator.get_required_accessories(product)
        recommended = self.validator.get_recommended_accessories(product)

        response = f"📦 **Requirements for {product}:**\n\n"

        if required:
            response += "**Required (must have):**\n"
            for req in required:
                response += f"  • {req}\n"
        else:
            response += "✅ No additional accessories required.\n"

        if recommended:
            response += "\n**Recommended (optional):**\n"
            for rec in recommended:
                response += f"  • {rec}\n"

        return response.strip()

    def _answer_conflict(self, product_1: str, product_2: str) -> str:
        """Answer: Does X conflict with Y?"""
        compatible, reason = self.validator.check_compatibility(product_1, product_2)

        if not compatible:
            return f"⚠️ **Yes, {product_1} conflicts with {product_2}**\n\n" f"Reason: {reason}"
        return f"✅ **No conflict between {product_1} and {product_2}**"

    def _answer_validate_config(self, base_product: str, accessories: list[str]) -> str:
        """Answer: Validate configuration"""
        is_valid, errors = self.validator.validate_configuration(base_product, accessories)

        config_str = f"{base_product} + " + " + ".join(accessories)

        if is_valid:
            response = "✅ **Configuration is VALID**\n\n"
            response += f"**Configuration:** {config_str}\n\n"
            response += "All compatibility checks passed!"

            # Show recommendations
            recommended = self.validator.get_recommended_accessories(base_product)
            missing_rec = [r for r in recommended if r not in accessories]
            if missing_rec:
                response += f"\n\n💡 **Consider adding:** {', '.join(missing_rec)}"

            return response
        response = "❌ **Configuration has ERRORS**\n\n"
        response += f"**Configuration:** {config_str}\n\n"
        response += "**Issues found:**\n"

        for error in errors:
            if error.severity == "error":
                response += f"  ❌ {error.message}\n"
            elif error.severity == "warning":
                response += f"  ⚠️ {error.message}\n"

        return response.strip()

    def _answer_recommendations(self, product: str) -> str:
        """Answer: What accessories are recommended for X?"""
        recommended = self.validator.get_recommended_accessories(product)

        if recommended:
            response = f"💡 **Recommended accessories for {product}:**\n\n"
            for rec in recommended:
                response += f"  • {rec}\n"
            return response.strip()
        return f"📌 No specific recommendations for {product}."

    def _answer_general(self, products: list[str]) -> str:
        """General information about products"""
        response = "📋 **Product Information:**\n\n"

        for product in products:
            if product not in self.validator.products:
                response += f"❌ {product}: Not found\n"
                continue

            info = self.validator.products[product]
            response += f"**{product}** ({info['product_type']})\n"

            # Show relationships
            required = self.validator.get_required_accessories(product)
            if required:
                response += f"  Requires: {', '.join(required)}\n"

            incompatible = self.validator.get_incompatible_products(product)
            if incompatible:
                response += f"  Conflicts with: {', '.join(incompatible)}\n"

            response += "\n"

        return response.strip()


# Example usage
if __name__ == "__main__":
    # Create agent and load data
    agent = ConfigurationAgent()

    # Register test data (in production, load from DB or JSON)
    agent.validator.add_product("C4080", "printer")
    agent.validator.add_product("MK-746", "finisher")
    agent.validator.add_product("MK-730", "bracket")
    agent.validator.add_product("SD-506", "finisher")
    agent.validator.add_product("SD-513", "finisher")
    agent.validator.add_product("PF-602m", "feeder")

    agent.validator.add_relationship("C4080", "MK-746", CompatibilityType.COMPATIBLE)
    agent.validator.add_relationship(
        "MK-746", "MK-730", CompatibilityType.REQUIRES, notes="MK-746 requires mounting bracket MK-730"
    )
    agent.validator.add_relationship(
        "SD-506", "SD-513", CompatibilityType.CONFLICTS, notes="Cannot install both saddle finishers simultaneously"
    )
    agent.validator.add_relationship(
        "C4080", "PF-602m", CompatibilityType.RECOMMENDED, notes="High-capacity feeder for production environments"
    )

    agent.loaded = True

    # Test questions
    print("=" * 60)
    print("Q1: Can I use MK-746 with C4080?")
    print("=" * 60)
    print(agent.ask("Can I use MK-746 with C4080?"))

    print("\n" + "=" * 60)
    print("Q2: What do I need for MK-746?")
    print("=" * 60)
    print(agent.ask("What do I need for MK-746?"))

    print("\n" + "=" * 60)
    print("Q3: Validate: C4080 + MK-746")
    print("=" * 60)
    print(agent.ask("Validate: C4080 + MK-746"))

    print("\n" + "=" * 60)
    print("Q4: Validate: C4080 + MK-746 + MK-730")
    print("=" * 60)
    print(agent.ask("Validate: C4080 + MK-746 + MK-730"))

    print("\n" + "=" * 60)
    print("Q5: Can I use SD-506 with SD-513?")
    print("=" * 60)
    print(agent.ask("Can I use SD-506 with SD-513?"))
