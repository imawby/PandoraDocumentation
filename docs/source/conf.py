# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'PandoraDocs'
copyright = '2026, Pandora Developers'
author = 'Pandora Developers'
release = '0.1.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = []

templates_path = ['_templates']
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_static_path = ['_static']
html_css_files = [
    'custom.css',
]

html_theme = 'sphinx_rtd_theme'
html_logo = '../../static/pandora_logo_square_bw.png'

html_theme_options = {
    'logo_only': True,
    'display_version': True,
}

# -- Options for EPUB output
epub_show_urls = 'footnote'
