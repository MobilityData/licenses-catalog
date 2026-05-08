# Contributing Guide

Thank you for your interest in contributing to this project!  
We welcome contributions to both the base code and the license content.

## Ways to Contribute

- **Fix or update an existing license summary** in `/data/licenses/`
- **Add a new license** (ensure it's OSI-approved)
- **Improve the code implementation and/or performance**
- **Report bugs** or inconsistencies via GitHub Issues
- **Suggest improvements to the documentation content and structure**

## Adding a License
You’re welcome to propose the addition of a new license if it meets the following basic criteria:

### Required Criteria
- The license must have a valid SPDX identifier. If not, please [submit it to SPDX first](https://github.com/spdx/license-list-XML/blob/main/CONTRIBUTING.md).

### How to Add a License

1. **Create a new file** in the `data/licenses/` folder  
   Use the SPDX identifier as the filename:  
   Example: `data/licenses/MIT.json`

2. **Follow the JSON structure** used by other licenses. _TBD_
   Each license file must include:
   - `spdx_id` (e.g., `"MIT"`)
   - `title`
   - `summary`
   - `license_url`
   - A list of standardized `rules` (see `data/rules.json`)
   - Optional metadata (e.g., OSI approval, FSF status, use cases)

3. **Ensure accuracy**
   - Match license text/metadata with the official SPDX entry
   - Provide examples or references in your pull request (e.g., popular repos using the license)
   - When reviewing generated `reasons`, check that `[verbatim]` evidence can be located verbatim in the license text, and that `[inferred]` entries are reasonable (see [`docs/RULES.md`](RULES.md#evidence-prefixes))

---

### Notes

- If the license is already included, consider improving its metadata or summary instead.
- If the license text differs from SPDX or includes special permissions/exceptions, note that clearly in the PR.


## License Reminder

- **All contributions to the repository content will be released under [CC0-1.0](https://creativecommons.org/publicdomain/zero/1.0/)**.
- **All code contributions must be compatible with the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).**

By contributing, you agree to license your changes under these terms.

Thank you!
