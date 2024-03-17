# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Compact Energy System Modeling Tool'
copyright = '2023, Sina Hajikazemi, Julia Barbosa'
author = 'Sina Hajikazemi, Julia Barbosa'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

# extensions = []
extensions = [
    'sphinx.ext.mathjax'
]

templates_path = ['_templates']
exclude_patterns = []

# myst_enable_extensions = [
#     "amsmath",
#     "attrs_inline",
#     "colon_fence",
#     "deflist",
#     "dollarmath",
#     "fieldlist",
#     "html_admonition",
#     "html_image",
#     "replacements",
#     "smartquotes",
#     "strikethrough",
#     "substitution",
#     "tasklist",
# ]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# html_theme = 'alabaster'
html_theme = 'sphinx_book_theme'
html_static_path = ['_static']
html_logo = "_static/logo.svg"
html_theme_options = {
    'logo_only': True,
    'display_version': False,
}