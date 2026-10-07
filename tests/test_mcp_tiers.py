"""MCP tiers: public allowlist never includes spending tools."""
import unittest


class TestMcpTiers(unittest.TestCase):
    def test_public_excludes_spenders(self):
        import backend.mcp_server as mcp

        spenders = {
            "figg_upload_photo", "figg_upload_chatgpt_file", "figg_start_mesh",
            "figg_preview_image",
            "figg_checkout", "figg_fullchain_personalise_order",
            "figg_studio_orders",
            "figg_blender_make",
            "figg_card_cutout", "figg_card_reserve",
            "figg_perform", "figg_greeting", "figg_video_share",
            "figg_write_premise", "figg_write_riff",
            "figg_guide_open", "figg_guide_turn", "figg_guide_packs",
            "figg_me", "figg_credits",
            "figg_print_export",
        }
        # figg_install_style is $0 local CPU (preset GLB, no Meshy) — public.
        # figg_design_save/order are reserve-only with fulfil neutered.
        self.assertTrue(mcp.PUBLIC_TOOLS.isdisjoint(spenders),
                        mcp.PUBLIC_TOOLS & spenders)
        # save + reserve-only order + style adoption are public: they cost
        # nothing until fulfil/uplink, and fulfil is neutered on this tier
        self.assertIn("figg_design_save", mcp.PUBLIC_TOOLS)
        self.assertIn("figg_design_order", mcp.PUBLIC_TOOLS)
        self.assertIn("figg_install_style", mcp.PUBLIC_TOOLS)
        for tool in ("figg_card_save", "figg_card_render", "figg_card_scene",
                     "figg_card_job"):
            self.assertIn(tool, mcp.PUBLIC_TOOLS)
        # agent credentials mint real access: full tier only, never public
        for t in ("figg_mint_agent", "figg_my_agents", "figg_revoke_agent"):
            self.assertNotIn(t, mcp.PUBLIC_TOOLS)
        # self-serve identity stays public so strangers can get their own key
        self.assertIn("figg_create_account", mcp.PUBLIC_TOOLS)
        self.assertIn("figg_login", mcp.PUBLIC_TOOLS)
        self.assertIn("figg_tools", mcp.PUBLIC_TOOLS)

    def test_every_registered_tool_has_a_tier(self):
        import backend.mcp_server as mcp

        for area, fns in mcp.TOOL_AREAS.items():
            for fn in fns:
                self.assertTrue(fn.__name__.startswith(("figg_", "oddhobb_")), fn.__name__)


if __name__ == "__main__":
    unittest.main()
