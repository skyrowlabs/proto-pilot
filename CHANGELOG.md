# Changelog

## [0.2.0](https://github.com/skyrowlabs/proto-pilot/compare/v0.1.0...v0.2.0) (2026-10-03)


### Added

* **archetypes:** extract crud, and make spec.screens authoritative ([b6b427a](https://github.com/skyrowlabs/proto-pilot/commit/b6b427acc407d3573bf287b631f68275e41b21da))
* **archetypes:** turn-based-game, and the axis holds ([04dfe7a](https://github.com/skyrowlabs/proto-pilot/commit/04dfe7a4e4bdf3d871b626d337302675aa608dbb))
* **clarify:** the question pass becomes the classifier, and answers stay typed ([8067d09](https://github.com/skyrowlabs/proto-pilot/commit/8067d0943b95a29be51cbac371faf0068d6a10d6))
* **console:** `proto console` — two panes over the job seam ([5c38ce3](https://github.com/skyrowlabs/proto-pilot/commit/5c38ce35c7d646d7788bc724b231f060d12512be))
* **console:** iterate on the prototype you have, instead of making another ([6eb594b](https://github.com/skyrowlabs/proto-pilot/commit/6eb594b630c865a9aa3d14c86be5c3f4a77a7892))
* **console:** resizable panes and a scrollable preview ([fbee5df](https://github.com/skyrowlabs/proto-pilot/commit/fbee5dfe9f4e858e48b9703b143a161736d71c34))
* **console:** run the generated prototype live in the pane ([37b4fcd](https://github.com/skyrowlabs/proto-pilot/commit/37b4fcd7cd2b591cc4dde077bc219ec751698955))
* **console:** show the generated app's own screen in a Preview tab ([5a70f84](https://github.com/skyrowlabs/proto-pilot/commit/5a70f8483a37f026c362fb584888134689c3000f))
* **console:** the skyrow palette, with one colour deliberately dropped ([5fa013b](https://github.com/skyrowlabs/proto-pilot/commit/5fa013b2f1e8a6182821f72f3193bc3bfffaec22))
* **console:** the spec review as a screen, and per-job stdout capture ([ef26232](https://github.com/skyrowlabs/proto-pilot/commit/ef26232e1899a5f111cae80de060c62c9bbea93c))
* **jobs:** a structured event channel beside the text log ([1685fda](https://github.com/skyrowlabs/proto-pilot/commit/1685fda3076a026d1b5e5759f6c4d476af83a6e9))
* **lifecycle:** make Docker self-describing, and stop ls deleting things ([a79e41b](https://github.com/skyrowlabs/proto-pilot/commit/a79e41bea8be697b7f0690faa57e7349c3c971bf))
* **skeleton:** split skeleton by target and add the terminal tree ([8a62e11](https://github.com/skyrowlabs/proto-pilot/commit/8a62e11df74c292b9b3b32dbcdacfa5ca8de6058))
* **spec:** give the spec a shape axis and a look axis ([d7a6cac](https://github.com/skyrowlabs/proto-pilot/commit/d7a6cac588d04214c271644ed89eba4692c374af))
* **spike:** measure the terminal target before building its seam ([23ea067](https://github.com/skyrowlabs/proto-pilot/commit/23ea067ac3dec0482527d6e5fcaa7889998d79f2))
* **targets:** make the output medium an axis, web behind it ([51f1b31](https://github.com/skyrowlabs/proto-pilot/commit/51f1b3128ecd972b57e09a1bcd99505087953bf9))
* **targets:** proto new builds a terminal app unless you say otherwise ([4a4adf8](https://github.com/skyrowlabs/proto-pilot/commit/4a4adf89b732a377dbdc4e1538c4456220473bad))
* **targets:** the terminal target's five passes and its baseline ([2dcc8d3](https://github.com/skyrowlabs/proto-pilot/commit/2dcc8d3638edc199b1a40a471441510c28945013))
* **theme:** the look axis, hidden from every pass that could misuse it ([aaa2f02](https://github.com/skyrowlabs/proto-pilot/commit/aaa2f02d1353e55b9200d3405d97ec3d0f40c621))
* **verify:** the terminal verifier, and a blank screen that fails it ([dd4a986](https://github.com/skyrowlabs/proto-pilot/commit/dd4a9866a6bd9db8ec5d884c297062f62fbddbdc))


### Fixed

* **ci:** `check health` describes the machine, not the CLI ([c2482e9](https://github.com/skyrowlabs/proto-pilot/commit/c2482e9136c299147813117b5fefc1b62163de0e))
* **ci:** `release-please` needed the `ui` job that the previous commit removed ([ee1653b](https://github.com/skyrowlabs/proto-pilot/commit/ee1653bfd6094aaf64e98dc5ec3816877b2a1964))
* **ci:** green locally is not green in CI, and now it means the same thing ([06395dd](https://github.com/skyrowlabs/proto-pilot/commit/06395dd19bec6cde721245c322cadecf3eb179d1))
* **cli:** preflight the backend before a front end takes the terminal ([6bcea04](https://github.com/skyrowlabs/proto-pilot/commit/6bcea042dbc4640d38dd97502e3ec83d4ad4158c))
* **console:** the path was correct, unreadable, and uncopyable ([96d64d6](https://github.com/skyrowlabs/proto-pilot/commit/96d64d6fec39321bae233d4a45739ea05e87e661))
* **docs:** make the documentation gates see what they claim to check ([2d05854](https://github.com/skyrowlabs/proto-pilot/commit/2d05854715d9e180c68758c880ba24c0cfa75478))
* **docs:** the link gate could not see NOTES.md, and said zero ([5ce7cd2](https://github.com/skyrowlabs/proto-pilot/commit/5ce7cd2c11caafccaea7b7025059aee21a1d48cb))
* **llm:** the write guard did not cover the claude-code backend ([6e02c85](https://github.com/skyrowlabs/proto-pilot/commit/6e02c85cb70407135f70d7377f06f553ce985dec))
* **skeleton:** escape on the first screen emptied the generated app ([4fba594](https://github.com/skyrowlabs/proto-pilot/commit/4fba5946d8ff024ed763af0352632dbe06bf2621))
* **skeletor:** re-derive ci.yml's hash from a base that exists ([434790a](https://github.com/skyrowlabs/proto-pilot/commit/434790abb02e9017b82f0e48915620032f8233b4))
* **skeletor:** take the DOCS_INDEX hash from the render, not from the tree ([a95a7cd](https://github.com/skyrowlabs/proto-pilot/commit/a95a7cd935d9cba692b4781f83d396976ee11021))
* **spec:** one implementation of spec assembly, and stop `add` wiping the axes ([c4906f8](https://github.com/skyrowlabs/proto-pilot/commit/c4906f8029f749f0e0b63750516f28ffd27feb96))
* **spike:** take away the MCP tools too, which --tools "" does not ([291593e](https://github.com/skyrowlabs/proto-pilot/commit/291593e36435fd34864c10af6905f08daabb151a))
* **tests:** a test that only ever skipped in CI is not a CI test ([602455e](https://github.com/skyrowlabs/proto-pilot/commit/602455ed4394132d305f774a812d044d215da178))
* **tui:** `make run` and `make test` failed where nothing needed building ([41d206f](https://github.com/skyrowlabs/proto-pilot/commit/41d206fec460af8f2e1b5301e85b9d6ca11ed091))
* **tui:** a generated terminal app could not be run on the machine that made it ([338d70b](https://github.com/skyrowlabs/proto-pilot/commit/338d70b46fe640b2bdae5d17fb0f70e1b4401dd3))
* **tui:** pin generated trees to sqlalchemy 2.1.1, what CI verifies with ([9baeb49](https://github.com/skyrowlabs/proto-pilot/commit/9baeb499a1df11c1512e3a0ef2b86243a5d12bf4))


### Documentation

* a reason that names a broken thing has an expiry nobody wrote down ([bdaa057](https://github.com/skyrowlabs/proto-pilot/commit/bdaa057cba6f98ee31e3dc56f227e11d611714ea))
* **ci:** take the version numbers back out of the comment that explains them ([1186019](https://github.com/skyrowlabs/proto-pilot/commit/1186019e59534f7b9be78261489e52690b13f514))
* **console:** file the proto Console plan to implementations/spec ([06e3693](https://github.com/skyrowlabs/proto-pilot/commit/06e3693ceb7d53e192d19ddc5339d92ebed6395a))
* **console:** Phase 1 measured — the seam is standalone and nothing arrives late ([754fada](https://github.com/skyrowlabs/proto-pilot/commit/754fadaef000c13fb32327d8815a367fd7b784f1))
* file Archetypes and Theme, and repoint the four things that cited it ([ecd0656](https://github.com/skyrowlabs/proto-pilot/commit/ecd0656991fe478d71604211c01405eb7e470611))
* fill every scaffold marker, and give health an owner ([576c570](https://github.com/skyrowlabs/proto-pilot/commit/576c57065fbe0bf4abe44065eb59b8aae1356b7a))
* **ideas:** table the hosted service, and point the tool at the terminal ([e7f0245](https://github.com/skyrowlabs/proto-pilot/commit/e7f02451ced9cdd5c1eb53d9981fe72ab67cb7cc))
* **notes:** close the skeletor item, which said it was waiting on them ([ac246d0](https://github.com/skyrowlabs/proto-pilot/commit/ac246d0c07b9a43f85cb8d968545e956d8011b42))
* **notes:** correct the upgrade trap, which blamed the wrong two things ([a2a0efd](https://github.com/skyrowlabs/proto-pilot/commit/a2a0efd50daab03fa01e255597ee030a4130a5f0))
* **notes:** record what the skeletor upgrade actually does, measured not assumed ([0c35c35](https://github.com/skyrowlabs/proto-pilot/commit/0c35c35e1a559bb3291872a078280d6e0035262b))
* **notes:** skeletor corrected the half I had guessed ([77c3772](https://github.com/skyrowlabs/proto-pilot/commit/77c37729b6ff7206ed92f546f1c950ed51d7bf9e))
* **notes:** the skeletor prune recipe expired; record the one that does not ([b228709](https://github.com/skyrowlabs/proto-pilot/commit/b228709a4a6c2d4b95322ef779fb56dd8ab979e1))
* **plan:** drawing freedom, ranked on verifiability rather than on Docker ([109eedf](https://github.com/skyrowlabs/proto-pilot/commit/109eedfafd05bd4fc2e2366cbb1e0b0a5ec2afa0))
* **plan:** re-scope the tank against the terminal pivot, and plan the target ([ade3de7](https://github.com/skyrowlabs/proto-pilot/commit/ade3de7d88d221c29142cd0573207d55647b665b))
* **plan:** the improvement loop, and the ratchet it turns on ([db08804](https://github.com/skyrowlabs/proto-pilot/commit/db088041a8ec0606f490ac1a3cdcd9d20ce05f3a))
* **plan:** the proto console — a front end for the tool, not for what it emits ([60003dc](https://github.com/skyrowlabs/proto-pilot/commit/60003dc26055dc7d1d15f93365708d02eae8fd69))
* **report:** the terminal gate passes, on a metric that measured nothing ([81eb7b7](https://github.com/skyrowlabs/proto-pilot/commit/81eb7b76a7c3aa7f71c32eef047a6d7c12368606))
* settle the network question by measurement, and record what it turned up ([d61e52e](https://github.com/skyrowlabs/proto-pilot/commit/d61e52e50e213f0988c5447a5a9cbd3725b2e364))
* **spike:** record what the first complete terminal run actually cost ([64a36bb](https://github.com/skyrowlabs/proto-pilot/commit/64a36bb674f5355135ea596fdecf7d14e9c2f388))
* **targets:** complete the terminal target — update docs, file to implementations ([f148f48](https://github.com/skyrowlabs/proto-pilot/commit/f148f484dfa1c0886d441c85ecfbac227376fb08))
* **theme:** what the live UI call proved, and the defect it found ([0af89dc](https://github.com/skyrowlabs/proto-pilot/commit/0af89dc792136b35b77201e0aebaea9c07a2daa9))
* **todo:** file the archetypes-and-theme plan ([1403f37](https://github.com/skyrowlabs/proto-pilot/commit/1403f373d2287e48ed4df358503e55ea8be7a7ef))
