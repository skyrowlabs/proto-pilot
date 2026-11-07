# Changelog

## [0.3.0](https://github.com/skyrowlabs/proto-pilot/compare/v0.2.1...v0.3.0) (2026-11-07)


### Added

* **llm:** ask the API in words for what it cannot enforce ([7726beb](https://github.com/skyrowlabs/proto-pilot/commit/7726beb2ba65f168b94cdc4e2683816e88c573df))
* **plan:** add a dream's scores and cap, and read what a topic says ([e9563e5](https://github.com/skyrowlabs/proto-pilot/commit/e9563e541710599929ea2d1d70a772b55f3bb69f))
* **plan:** add offline proto plan, its model and renderer ([3712c5c](https://github.com/skyrowlabs/proto-pilot/commit/3712c5ce758a8c01f05cc8e65c40182b98b0b3e0))
* **plan:** add proto dream, and let a person promote or drop a dream ([3edee0c](https://github.com/skyrowlabs/proto-pilot/commit/3edee0c4e798bbc7e14e7acb56b256a4c291d44f))
* **plan:** add the scope, outline, connect, consider and start passes ([beeb926](https://github.com/skyrowlabs/proto-pilot/commit/beeb926375fbe3a7ede792ff5588be502850b46d))
* **plan:** dream as a plan is made, and survive dreaming failing ([0c67a10](https://github.com/skyrowlabs/proto-pilot/commit/0c67a10f0c796fc3e6eaa8c28a97ad61a274f368))
* **plan:** dream extensions of the idea, apart from the plan ([f6295c9](https://github.com/skyrowlabs/proto-pilot/commit/f6295c92240aeff7b2377d1ab29c637a1c2f9d0e))
* **plan:** model passes, outline review and --depth ([2f93629](https://github.com/skyrowlabs/proto-pilot/commit/2f9362943116f59f4ae71c3c910abe251fb6a64d))
* **plan:** offline proto plan with model, baseline and renderer ([df89ea9](https://github.com/skyrowlabs/proto-pilot/commit/df89ea90d579321c1cf2fc2a6ed66cf73650d2a1))
* **plan:** record depth and summarise a plan for review ([02d6b4e](https://github.com/skyrowlabs/proto-pilot/commit/02d6b4ebfd2874057c6e91941afdb027ca676707))
* **plan:** repair a red plan, bounded, and hand back what stays red ([512bc9d](https://github.com/skyrowlabs/proto-pilot/commit/512bc9d0dccd981b763754d2c0eb632e932aba39))
* **plan:** run the passes behind an outline checkpoint and --depth ([5b152c7](https://github.com/skyrowlabs/proto-pilot/commit/5b152c77f4c0ddc6a886bc1816e3edd459691573))
* **plan:** verify a plan's structure and repair what it can ([a8ab663](https://github.com/skyrowlabs/proto-pilot/commit/a8ab663368b0e1e1e6d177633f0ec954db1d531d))
* **plan:** verify a plan's structure, one named check per bullet ([b66bc9e](https://github.com/skyrowlabs/proto-pilot/commit/b66bc9ed53cd45e74a887785b8fdd4c50c68cdf9))


### Fixed

* **cli:** lead the first thing a user reads with planning ([bbcedc4](https://github.com/skyrowlabs/proto-pilot/commit/bbcedc41f7c6263b732b300821b3d7180cb9f9f9))
* **plan:** harden render order, stale sweep, slugs and citations ([1d171d2](https://github.com/skyrowlabs/proto-pilot/commit/1d171d205de51507b2ac3952848e61c2c766df67))
* **plan:** judge a repair against the plan repair started from ([33cb511](https://github.com/skyrowlabs/proto-pilot/commit/33cb51129ee94395cc1310365182ee3dfede649d))
* **plan:** keep dreams from costing a plan, and a verb from half landing ([2f14a0b](https://github.com/skyrowlabs/proto-pilot/commit/2f14a0bb2db2889abb33cb15ba0d8ae2bb3adbbf))
* **plan:** keep the floor honest and everything inside the tree ([809ddab](https://github.com/skyrowlabs/proto-pilot/commit/809ddab7b3cd798d7148cc82946fa0256f5a1f17))
* **plan:** name what blocks a page instead of a raw OSError ([3b6a886](https://github.com/skyrowlabs/proto-pilot/commit/3b6a88648005d6f9658d69770ed3a26d4bf09589))
* **plan:** offer start every topic and let the walk hold the order ([4e5d274](https://github.com/skyrowlabs/proto-pilot/commit/4e5d27424b986211ae026c48add9ac71978e4275))
* **plan:** refuse an existing plan for a different idea ([0ba56d5](https://github.com/skyrowlabs/proto-pilot/commit/0ba56d59d1c43226220f770c39dc4d08a7ef6e92))
* **plan:** save atomically and refuse a plan that appears before it ([63c51a1](https://github.com/skyrowlabs/proto-pilot/commit/63c51a156b4842c56c14f2a467c26a49df5ed0ac))
* **plan:** say what a repair did to step text, and how to retry offline ([897f37e](https://github.com/skyrowlabs/proto-pilot/commit/897f37ec72719a514b129eda7984088ecd95907d))
* **plan:** write the entry page last so PLAN.md means every page ([7bc303f](https://github.com/skyrowlabs/proto-pilot/commit/7bc303f14c0df14d6af1ad1d8d3d0a9f414e378d))
* **test:** type a parametrized index so pyright reads one dream ([cd3e3c1](https://github.com/skyrowlabs/proto-pilot/commit/cd3e3c165d87f7ba0225d201165f2080ab371bd7))


### Documentation

* **architecture:** name plan.json without citing a path ([76354ba](https://github.com/skyrowlabs/proto-pilot/commit/76354ba5f1b174f5b41666b2cbead9544c95e597))
* **ideas:** pivot the product to planning, table prototyping ([d867d88](https://github.com/skyrowlabs/proto-pilot/commit/d867d887f762c9ef3d3b66f183eae3fb7bf54981))
* **ideas:** pivot the product to planning, table prototyping ([d3c116a](https://github.com/skyrowlabs/proto-pilot/commit/d3c116a39e7265b0fc896d44adc550edc06640ed))
* **plan:** describe dreaming as built ([5a15095](https://github.com/skyrowlabs/proto-pilot/commit/5a15095d59764ff29a2932aa94cdcd6f6f15064d))
* **plan:** describe the model-backed proto plan run ([88d09b7](https://github.com/skyrowlabs/proto-pilot/commit/88d09b73feff7771071a0b03bbac810ee7c9549a))
* **plan:** describe verification, repair and the floor ([5bbc527](https://github.com/skyrowlabs/proto-pilot/commit/5bbc527bf89bae7d00a039717bdd8755b10ad46e))
* **plan:** map the offline plan pipeline for agents and readers ([0722c8a](https://github.com/skyrowlabs/proto-pilot/commit/0722c8ad8c7ee3721a45436f7857181c051b16df))
* **plan:** tick Phase 4 of the plan ([9d38ad5](https://github.com/skyrowlabs/proto-pilot/commit/9d38ad5f519f37a302735eecf0b3b25ffba9fca7))
* **plan:** tick the Phase 5 boxes that landed ([4b57fb7](https://github.com/skyrowlabs/proto-pilot/commit/4b57fb744d6607ac5b552e18cc7ab8272d604f17))
* **readme:** lead with planning, move prototyping later ([eff2b62](https://github.com/skyrowlabs/proto-pilot/commit/eff2b623b284f9d6fef54d65c42023a6760fbeeb))
* **readme:** lead with planning, move prototyping later ([35fb458](https://github.com/skyrowlabs/proto-pilot/commit/35fb458b358d9c0c8a83bf242abfa9a35e0a983d))
* **readme:** show the verify step in the example run ([4df781c](https://github.com/skyrowlabs/proto-pilot/commit/4df781c390c297cffc339dffa93f466a131c9e41))
* **reports:** refresh the repository report for v0.2.1..HEAD ([156049d](https://github.com/skyrowlabs/proto-pilot/commit/156049d0b40b6500605346ec2dab5887a2785768))
* **todo:** plan prototypes and dreaming, a draft spec ([50baf87](https://github.com/skyrowlabs/proto-pilot/commit/50baf87a656b6891fbf6deda992b820b1b72b51b))
* **todo:** plan prototypes and dreaming, a draft spec ([1c2d365](https://github.com/skyrowlabs/proto-pilot/commit/1c2d3652ef77cc1279aefc3ae3857aca6356a737))
* **todo:** record Phase 1 and mark plan-prototypes ready ([89cf722](https://github.com/skyrowlabs/proto-pilot/commit/89cf7220d08fecaaeb01c46aa53c28cbf3628997))
* **todo:** record the plan-prototypes rulings ([8d221fb](https://github.com/skyrowlabs/proto-pilot/commit/8d221fb67525d2ebd5d6fa2042f6f84816a9e505))
* **todo:** record the plan-prototypes rulings ([c715a28](https://github.com/skyrowlabs/proto-pilot/commit/c715a28b147c467697f372059b755a39a2018ac4))
* **todo:** tick Phase 3 of plan-prototypes ([df21723](https://github.com/skyrowlabs/proto-pilot/commit/df21723b5884d2f9da376985c245dd6293ac82e5))

## [0.2.1](https://github.com/skyrowlabs/proto-pilot/compare/v0.2.0...v0.2.1) (2026-11-05)


### Fixed

* **docs:** the Quick Start installs proto.pilot with every extra ([ff1332f](https://github.com/skyrowlabs/proto-pilot/commit/ff1332fc640f98558900e14174c3d79beec97fef))


### Changed

* **docs:** take skeletor's check_doc_tables byte for byte ([ef14963](https://github.com/skyrowlabs/proto-pilot/commit/ef149632878db58d34fccda065c6e7e43a83880a))


### Documentation

* **readme:** add the skyrow hero and theme ([1c185e7](https://github.com/skyrowlabs/proto-pilot/commit/1c185e7b948fe7e9da431b885065df8d900bad94))
* **readme:** bring the badge row to the workspace standard ([2bf5ca7](https://github.com/skyrowlabs/proto-pilot/commit/2bf5ca7b2beb3436282c5274aee0868554699bcb))
* **reports:** close the v0.2.0 report window ([af32686](https://github.com/skyrowlabs/proto-pilot/commit/af32686dfdf160929bbac9b045a42e1de2b6b9e5))
* **reports:** record the v0.2.0 window that froze no reports ([8ac5800](https://github.com/skyrowlabs/proto-pilot/commit/8ac5800c8df88dedd6ba3c6b5a1c2cc3c3970bfd))
* **reports:** refresh the repository report for v0.2.0..HEAD ([1c1a6db](https://github.com/skyrowlabs/proto-pilot/commit/1c1a6dbd9f89c19f9950c92168410216946cbeb9))
* **reports:** refresh the repository report for v0.2.0..HEAD ([b4545f3](https://github.com/skyrowlabs/proto-pilot/commit/b4545f353bbfef645922f6d2bed7344575116d99))
* **reports:** refresh the repository report for v0.2.0..HEAD ([4e056f2](https://github.com/skyrowlabs/proto-pilot/commit/4e056f248ba35692d9cfde7bac167a43989957dc))

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
