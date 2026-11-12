# How this repository was made (Eurasian Economic Union)

This file is written by the build on 2026-11-12, the day the source data was retrieved.

## Sources

| Source | Address | Retrieved | Licence |
| --- | --- | --- | --- |
| Правовой портал Евразийского экономического союза | <https://docs.eaeunion.org/docs/ru-ru/0053610/itia_05062014> | 2026-11-12 | No express text licence stated on the page; © Евразийский экономический союз, 2026. |

Every word of law in this repository comes from these sources. Lexifina reads them and records each act's dated versions, and the laws that made each change, in one corpus file. This repository is built from that file.

## What is in it

| Act | Title | Versions | Span |
| --- | --- | ---: | --- |
| `dogovor-o-evraziyskom-ekonomicheskom-soyuze` | Договор о Евразийском экономическом союзе | 1 | 2015-01-01 to 2015-01-01 |

The build made 1 commits:

| Commits | Kind |
| ---: | --- |
| 0 | baseline texts where the record starts |
| 1 | named laws, court decisions and treaties |
| 0 | changes no amendment note explains, credited to the publisher |
| 0 | corrections to the existing record |
| 0 | printing or layout changes |

Other counts:
- 0 commits on the branch `futuro`: laws not yet in force on 2026-11-12.
- 0 commits dated 1 January 1970: in force before 1970, with the real day in their `In-force` trailer.
- 1 laws in the record.
- 2 tags.

## Dates

Each commit is dated at noon (Europe/Moscow) on the day the change took effect. The other dates, enacted and published, are trailers.

When a law gives no date of its own, the default rule applies: Entry into force is taken from each document's own portal metadata. https://docs.eaeunion.org/docs/ru-ru/0053610/itia_05062014

## How the history is built

`tools/build.py` turns the corpus into this history in one pass: one commit per law, on the day it took effect. The same corpus always gives the same commit hashes. `tools/check_repo.py` reads every version back from git and compares it with the corpus. `tools/on.py` shows the law as it stood on any date. The corpus format is described in `tools/SCHEMA.md`.

- Corpus: sha256 `07d850f79d675f2f379b057dca0da41a9edc33946aabca8e0ad38782a1edc91d` (363330 bytes).
- Builder blob hashes (`git hash-object`): `build.py` `63170edd89e92292ac248dae17d79e486e4e9f19`, `check.py` `e340718c28cd5b0edbe37bdeab1aac31427ada66`, `on.py` `4a8aa1c9a5e6bd8cc831b90a6e68c5a6f448a13c`.
- Python 3.12.10; git version 2.46.0.windows.1.

## Checks

Not yet run for this build.

No second build of this corpus has been compared yet.

## Decisions made by hand

- The official portal states 29 May 2014 adoption, 5 June 2014 publication and 1 January 2015 entry into force.
- The Word member in the portal's Russian attachment ZIP is the signed Treaty, not a later consolidation.
- Annexes and later amending protocols are not claimed as part of this checked version.

## What AI did and did not do

The source readers and builders were developed under Lexifina's direction with coding assistants, including Claude Code and Codex.

No model wrote, translated or corrected legal text. No model runs at build time. Every word of law in this repository comes from the official sources above.

The commit messages are written by `build.py` from the source data.

Model use at data-build time:
- A model wrote parsing code and metadata; legal words came only from the official Word file.
