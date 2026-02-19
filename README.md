# Licenses Catalog

A developer-friendly tool to explore, compare, and integrate software and data licenses.
Inspired by [choosealicense.com](https://github.com/github/choosealicense.com), with added metadata and API access for automation.

## Why This Project Exists

The [choosealicense.com](https://github.com/github/choosealicense.com) is a great reference, but it has some limitations:

- It is **GitHub-specific**, reflecting GitHub’s policy on license visibility and use.
- It **limits the number of licenses shown**, omitting many OSI-approved or widely-used alternatives.
- It focuses more on **encouraging license use** than on **neutral license comparison**.

This repository is intended to provide:
- A **more complete and neutral catalog** of software and data licenses
- **Machine-readable** metadata and formats for seamless integration and reuse in tools, websites, and automated systems
- A **human-oriented** structure that presents license details in a clear and accessible way for both people and tools.

## License Rules and Metadata

Each license includes a list of `rules` declared in [`data/rules.json`](data/rules.json). These are grouped into three categories:

- **Permissions** – What the license explicitly allows (e.g., commercial use, modification)
- **Conditions** – What the license requires (e.g., attribution, share-alike)
- **Limitations** – What the license prohibits or disclaims (e.g., warranty, liability)

The full set of rules is defined in [`rules.json`](data/rules.json). See the complete rule documentation in [`/docs/RULES.md`](/docs/RULES.md).


## License

- Code licensed under the [Apache 2.0 License](http://www.apache.org/licenses/LICENSE-2.0).
- Content under the [CC0 1.0 Universal Public Domain Dedication](https://creativecommons.org/publicdomain/zero/1.0/legalcode).

## Contributing

Please check out our [Contributing guide](/docs/CONTRIBUTING.md) for details.
