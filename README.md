# Pandora Documentation

### Building the Docs

Requirements:

- Python 3.13+
- uv
- Doxygen (if building doxygen API reference locally)
- Graphviz (for Doxygen call graphs — optional but recommended)

Instructions:

```bash
# Clone the repository with submodules...
# You can skip the submodules if you only want to build the Sphinx user docs, but you'll need them for the Doxygen API reference.
#
# If you change your mind you can do
#
# git submodule update --init --recursive
#
# to get the submodules later.
git clone --recurse-submodules https://github.com/PandoraPFA/PandoraDocumentation.git
cd PandoraDocumentation

# Set up the Python environment and install dependencies
uv sync

# Build the Sphinx user docs
cd docs && make html

# Build the Doxygen API reference
cd ../doxygen && doxygen Doxyfile
```

This will produce two sets of documentation:

 - `docs/build/html/` - User facing documentation built with Sphinx.
 - `doxygen/html/` - API reference built with Doxygen.

## Deployment

The docs are deployed automatically to GitHub Pages on every push to `main` via the [deploy-docs workflow](.github/workflows/deploy-docs.yml):

| URL | Content |
|-----|---------|
| `https://pandorapfa.github.io/PandoraDocumentation/` | User docs (Sphinx) |
| `https://pandorapfa.github.io/PandoraDocumentation/dev/` | API reference (Doxygen) |

---

### Third Party Licenses

The following third party software is used in the generation of this documentation. Please refer to the respective license files for more information.

- [Doxygen](https://www.doxygen.nl/index.html) - [GPL-2.0 License](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html)
- [Sphinx](https://www.sphinx-doc.org/en/master/) - [BSD License](https://opensource.org/licenses/BSD-3-Clause)
- [Doxygen Awesome Theme](https://github.com/jothepro/doxygen-awesome-css) - [MIT License](https://opensource.org/licenses/MIT)
