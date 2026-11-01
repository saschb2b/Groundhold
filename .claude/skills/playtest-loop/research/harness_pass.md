# A second pass: the genre, recruiting by experience, and LLM testers

Written while the harness was reviewed (1 November 2026), beside `methods.md` and
`wc3_veteran.md`, and folded into the personas.


The owner's brief: long years of Warcraft III custom-map tower defense are the crucial base.
Groundhold's design is built from that lineage, and the persona is its judge.

- **The genre's root is the persona's past.** The Frozen Throne (2003) shipped a hidden TD
  scenario, and Element TD and Gem TD were World Editor maps by 2006, before the Flash wave of
  2007 (Flash Element TD, Desktop Tower Defense) and the standalone games after it
  ([Wikipedia, Tower defense](https://en.wikipedia.org/wiki/Tower_defense)). Legion TD was a
  WC3 map from the late 2000s before Legion TD 2 (2017)
  ([Wikipedia, Legion TD](https://en.wikipedia.org/wiki/Legion_TD)). Groundhold borrows that
  vocabulary on purpose: a command card on Q W E / A S D, forks as upgrade trees, checks a wave
  brings (swarm, swift, armoured, winged, boss) and a send-for-income duel, the Drift, whose
  originality guard names "the genre's send-for-income convention" and Legion TD 2
  (`docs/design/core-loop.md` 1.4). A veteran of those maps is the player who notices where
  Groundhold keeps a convention, breaks one, or copies one too closely.
- **What veterans of those maps valued:** fast, exact early builds; gold timing (spend now or
  hold for the next income tick); creativity inside the map's rules; sends as the tension
  between defending and pressuring; coordination by chat. What hurt the maps: versions that
  changed rules from lobby to lobby, a broken tower each version tried to fix, empty lobbies
  ([Maul Tactics, Wintermaul Wars](https://maultactics.gg/articles/wintermaul-wars-history);
  [the maps that became games](https://maultactics.gg/articles/wc3-custom-maps-standalone-games),
  a developer's own blog, so read as one voice). The most played WC3 TD maps each had one
  defining rule: Green TD's sixty waves, Element TD's element picks, Wintermaul One's creep
  types that each want a different tower, Line Tower Wars' and Legion TD's sends
  ([GIGA](https://www.giga.de/tipp/die-beliebtesten-tower-defense-maps-im-ueberblick-warcraft-3-reforged/)).
- **What today's TD players reward and punish** (summaries of Steam reviews, so rough signals):
  depth, tower synergies and co-op roles are praised; repetition, weak balance, missing
  co-op communication and low frame rates with many creeps are punished
  ([Element TD 2](https://vaporlens.app/app/1018830/element_td_2_tower_defense)). Legion TD 2's
  reviewers praise that it "feels like a Warcraft III custom map", and worry that veterans
  dominate and newcomers struggle ([TechRaptor](https://techraptor.net/gaming/reviews/legion-td-2-review);
  [a Steam discussion, 2020](https://steamcommunity.com/app/469600/discussions/0/3830828948526350151)).
- **Define a playtester by experience and behaviour, not demographics.** Games user research
  screens playtesters by how much they play a genre, checked with knowledge-based questions
  only a real player answers ([PlaytestCloud](https://start.playtestcloud.com/blog/the-art-of-player-recruitment/)),
  and "recruiting based on age and gender amongst adults is not recommended"
  ([Games User Research, Preparing a study](https://gamesuserresearch.com/?p=2667)). So the
  persona names the maps and games it played and what it knows of them; its age only dates the
  era it played in.
- **Three dimensions make an LLM tester consistent and distinct.** PersonaTester (FSE 2026)
  built its tester personas from 1,500 human testing traces along testing mindset, exploration
  strategy and interaction habit; agents given those personas behaved alike within a persona,
  apart across personas, and triggered more bugs than agents without one
  ([arXiv 2603.24160](https://arxiv.org/abs/2603.24160)). Each persona's block says all three: how it
  judges, in what order it explores, how its hands work.
- **A real player's goals change during play.** Procedural personas with one fixed goal miss
  how players move from learning to optimising; goal sequences fit players better
  ([Playtesting: what is beyond personas](https://arxiv.org/abs/2107.11965)). Each persona's "How you take on a
  new TD" is that sequence, and each session's goals steer it.
- **Guard against caricature.** LLM simulations of a persona exaggerate its traits
  ([CoMPosT, EMNLP 2023](https://aclanthology.org/2023.emnlp-main.669)), and models that follow
  persona instructions closely polarise most
  ([The Chameleon's Limit, 2026](https://arxiv.org/abs/2604.24698), a preprint). So each block
  says a persona's years show in what it notices, not in voice, and the score is anchored to
  what it would do (come back, bring friends), not to a mood.
- **LLM agents play worse than people but measure difficulty usefully**
  ([Xiao and Yang, 2024](https://arxiv.org/abs/2410.02829)). A loss a persona reports is checked
  by replay and the sim harness before a number moves (SKILL.md, Triage).
