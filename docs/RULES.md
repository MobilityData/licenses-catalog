## License Rules and Metadata

Each license includes a list of `rules` declared in `data/rules.json`. These are grouped into three categories:

- **Permissions** – What the license explicitly allows (e.g., commercial use, modification)
- **Conditions** – What the license requires (e.g., attribution, share-alike)
- **Limitations** – What the license prohibits or disclaims (e.g., warranty, liability)

### Permissions

| Name                   | Label                | Description                                                                                  |
| ---------------------- | -------------------- | -------------------------------------------------------------------------------------------- |
| `commercial-use`       | Commercial use       | This license allows the software or data to be used for commercial purposes.                 |
| `modifications`        | Modification         | This license allows the software or content to be modified.                                  |
| `distribution`         | Distribution         | This license allows the software or content to be redistributed.                             |
| `private-use`          | Private use          | This license allows private use and modification.                                            |
| `patent-use`           | Patent use           | This license includes an express grant of patent rights from contributors.                   |
| `data-use`             | Data use             | This license allows unrestricted use and reuse of data.                                      |
| `text-and-data-mining` | Text and data mining | This license explicitly permits automated analysis such as machine learning and data mining. |
| `create-adaptations`   | Create adaptations   | This license allows derivative works or adaptations to be created.                           |

### Conditions

| Name                        | Label                           | Description                                                                                    |
| --------------------------- | ------------------------------- | ---------------------------------------------------------------------------------------------- |
| `include-copyright`         | Include copyright               | A copy of the license and copyright notice must be included.                                   |
| `include-copyright--source` | Include copyright (source only) | A copyright notice must be included only in the source form.                                   |
| `document-changes`          | Document changes                | Changes made must be clearly documented.                                                       |
| `disclose-source`           | Disclose source                 | Source code must be made available when the software is distributed.                           |
| `network-use-disclose`      | Network use disclosure          | Source must be disclosed when users interact with the software over a network.                 |
| `same-license`              | Same license                    | Modifications must be released under the same or a compatible license.                         |
| `same-license--file`        | Same license (file)             | Modified files must retain the original license.                                               |
| `same-license--library`     | Same license (library)          | Modifications to libraries must retain the original license, with some exceptions for linking. |
| `attribution`               | Attribution                     | Users must give appropriate credit to the original authors.                                    |
| `mark-changes`              | Mark changes                    | Users must indicate if changes were made.                                                      |
| `share-alike`               | Share-alike                     | Derivative works must be distributed under the same or a compatible license.                   |
| `non-endorsement`           | Non-endorsement                 | The license prohibits implying endorsement by the original authors.                            |
| `license-linking`           | License linking                 | The license must be referenced or linked clearly in any reuse.                                 |

### Limitations

| Name                         | Label                      | Description                                                                     |
| ---------------------------- | -------------------------- | ------------------------------------------------------------------------------- |
| `trademark-use`              | Trademark use              | The license does not grant rights to use trademarks.                            |
| `patent-use`                 | Patent use                 | The license explicitly excludes or does not waive patent rights.                |
| `liability`                  | Liability disclaimer       | The license includes a limitation of liability.                                 |
| `warranty`                   | No warranty                | The license explicitly states that no warranty is provided.                     |
| `no-personal-data-guarantee` | No personal data guarantee | The license disclaims the presence or legality of personal data in the content. |
| `database-rights-disclaimed` | Database rights disclaimed | The license explicitly waives or disclaims sui generis database rights.         |

---

## Classification Evidence (`reasons`)

Every selected rule in `permissions`, `conditions`, and `limitations` is accompanied by an evidence object stored under the `reasons` key in each license JSON file. This provides traceability for each classification decision.

```json
"reasons": {
  "permissions": {
    "commercial-use": ["[verbatim] \"to use, copy, modify, merge, publish... and/or sell copies\""]
  },
  "conditions": {
    "include-copyright": ["[verbatim] \"The above copyright notice... shall be included in all copies\""]
  },
  "limitations": {
    "warranty": ["[verbatim] \"THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND\""]
  }
}
```

### Evidence Prefixes

Each evidence string must begin with one of two prefixes that indicate how the rule was derived:

| Prefix | Meaning | When to use |
| ------------ | ------- | ----------- |
| `[verbatim]` | Directly quotes or tightly paraphrases a specific clause or section in the license text. | A clear statement in the license explicitly grants, requires, or restricts something. |
| `[inferred]` | The rule is implied rather than stated (e.g., a broad grant with no contrary restriction, or the absence of a prohibition). | No single clause names the rule directly; the classification follows from the overall grant or from the absence of a restriction. |

If a single thought combines a quote with an inference, it should be split into two evidence strings — one `[verbatim]` for the supporting clause and one `[inferred]` for the conclusion drawn from it.

### Reviewing Evidence

When reviewing a classification pull request:

- **`[verbatim]` entries** can be verified directly against the license text.
- **`[inferred]` entries** require judgment: confirm that the license text truly contains no contrary restriction and that the inference is reasonable.
- Any rule supported only by `[inferred]` evidence warrants extra scrutiny before approval.
