"""MCP tiers: the public surface is six intent tools, nothing else."""
import unittest


CANONICAL_SIX = {
    "oddhobb_people",
    "oddhobb_make",
    "oddhobb_change",
    "oddhobb_get",
    "oddhobb_add_media",
    "oddhobb_buy",
}


class TestMcpTiers(unittest.TestCase):
    def test_public_is_exactly_the_six(self):
        import backend.mcp_server as mcp

        self.assertEqual(set(mcp.PUBLIC_TOOLS), CANONICAL_SIX)

    def test_machinery_needs_a_key(self):
        import backend.mcp_server as mcp

        for tool in ("figg_card_save", "figg_card_render", "figg_card_scene",
                     "figg_card_job", "figg_card_create", "figg_card_update",
                     "figg_card_for_person", "figg_card_templates",
                     "figg_card_fonts", "figg_card_messages",
                     "figg_card_edit", "figg_card_variants",
                     "figg_card_library", "figg_card_cutout",
                     "figg_card_reserve", "figg_card_checkout",
                     "figg_card_gallery", "figg_card_reroll",
                     "oddhobb_make_card", "oddhobb_deal_cards",
                     "oddhobb_attach_card_art", "oddhobb_edit_card_copy",
                     "oddhobb_checkout_card", "oddhobb_recommend",
                     "oddhobb_regenerate_title_art",
                     "oddhobb_ideas", "oddhobb_create",
                     "oddhobb_render", "oddhobb_status",
                     "oddhobb_providers", "oddhobb_capsule",
                     "oddhobb_review", "oddhobb_revise",
                     "figg_tools", "figg_create_account", "figg_login"):
            self.assertNotIn(tool, mcp.PUBLIC_TOOLS, tool)

    def test_every_registered_tool_has_a_tier(self):
        import backend.mcp_server as mcp

        for area, fns in mcp.TOOL_AREAS.items():
            for fn in fns:
                self.assertTrue(fn.__name__.startswith(("figg_", "oddhobb_")), fn.__name__)


if __name__ == "__main__":
    unittest.main()
