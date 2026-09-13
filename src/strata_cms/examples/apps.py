"""Optional Django AppConfig demonstrating explicit plugin registration."""

from strata_cms.examples.simple_article import EXAMPLE_ARTICLE, EXAMPLE_PLUGIN
from strata_cms.examples.structured_page import LANDING_PAGE, SECTION_BLOCK, TEXT_BLOCK
from strata_cms.plugin_api.django import StrataPluginConfig
from strata_cms.plugin_api.registry import PluginRegistrar


class ExampleArticlePluginConfig(StrataPluginConfig):
    """Example plugin; installed only by automated test settings."""

    name = "strata_cms.examples"
    label = "strata_example_article"
    strata_plugin = EXAMPLE_PLUGIN

    def register_strata(self, registrar: PluginRegistrar) -> None:
        """Register example content and blocks through the scoped registrar."""
        registrar.register_block_type(TEXT_BLOCK)
        registrar.register_block_type(SECTION_BLOCK)
        registrar.register_content_type(EXAMPLE_ARTICLE)
        registrar.register_content_type(LANDING_PAGE)
