# Research brief: LLM playtester personas for Groundhold

Researched online on 1 November 2026 for the personas in `../personas/`. Statements marked **(inference)** are conclusions drawn for this project, not findings from the sources.

## 0. Bottom line

1. **Ground the persona in real player writing.** Long, invented backstories make simulated personas less faithful. More LLM-generated persona detail made simulated opinions more skewed ([Li et al., NeurIPS 2025](https://arxiv.org/abs/2503.16527)). Agents built from two-hour interview transcripts matched people's survey answers at 85% of those people's own two-week self-consistency, and were less biased than agents given demographic descriptions ([Park et al. 2024](https://arxiv.org/abs/2411.10109)). MeepleLM built its five board-game personas by clustering 150K real reviews ([Li et al., ACL 2026](https://arxiv.org/html/2601.07251v1)).
2. **Expect positivity and central tendency by default, and design against them.** General-purpose LLMs grouped game ratings around "safe, high scores (7–9)" and missed negative feedback ([MeepleLM](https://arxiv.org/html/2601.07251v1)). NN/g's synthetic users praised every idea and "seem to care about everything" ([Rosala & Moran 2024](https://www.nngroup.com/articles/synthetic-users/)).
3. **Problems are only as good as their evidence.** People "don't know why they do what they do" ([Valve, GDC 2009](https://cdn.fastly.steamstatic.com/apps/valve/2009/GDC2009_ValvesApproachToPlaytesting.pdf)), and an LLM's stated reasoning can leave out what actually drove its output ([Turpin et al. 2023](https://arxiv.org/abs/2305.04388)). Every problem should cite frames and actions, with observation, interpretation and suggestion kept apart.
4. **Use several personas, and if possible more than one model.** Different evaluators find different problems ([evaluator effect](https://measuringu.com/evaluator-effect/)). One GUI playtester's priorities "vary substantially across model backbones" ([Play2Code, 2026](https://arxiv.org/abs/2605.28258)). A panel of mixed model families reduces a single judge's self-bias ([Verga et al. 2024](https://arxiv.org/abs/2404.18796)).
5. **Hide earlier scores and patch notes until the blind rating is written.** Prior scores shown only as metadata still pulled LLM judges toward them, and telling the model to ignore them did not remove the effect ([Kapetanovic et al. 2026](https://arxiv.org/abs/2608.25869)). Feedback also turns more positive when the user signals they like or wrote the work ([Sharma et al., ICLR 2024](https://arxiv.org/abs/2310.13548)).
6. **Treat the loop's output as hypotheses, not player truth.** NN/g says synthetic research is for hypotheses and preparation and must not replace real users ([NN/g](https://www.nngroup.com/articles/synthetic-users/)).

## 1. What games user research says

**Motivation models.** Quantic Foundry's Gamer Motivation Model has 12 motivations in six pairs: Action, Social, Mastery, Achievement, Immersion and Creativity ([review, PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9872527)). The company presents them as related facets, not buckets to sort players into ([Quantic Foundry](https://quanticfoundry.com/2015/12/21/map-of-gaming-motivations/)). Nick Yee argued that assessments built on Bartle's types may create types rather than measure them, and that the labels group motivations that don't actually correlate ([Yee](https://nickyee.com/daedalus/archives/001298.php)). BrainHex "lacks empirical validation" of its psychometric properties ([Tondello et al. 2018](https://uwaterloo.ca/scholar/node/18198)).
- Competition is the motivation that falls most with age, mostly between 13 and 35. Strategy is the most stable ([Quantic Foundry](https://quanticfoundry.com/2016/08/11/appeal-of-competition/), [also](https://quanticfoundry.com/?p=2400)).
- **(inference)** Write a persona as a scored motivation profile, not a type label. A Warcraft III TD veteran who played around 2004–2012 is now in their 30s or 40s, so expect high Strategy and lower Competition. That is a reason to give the duelist its own persona.

**Whom to recruit.** A course deck summarising Schell's *Art of Game Design* makes four points ([deck](https://stewart.sdsu.edu/cs583_spr2013/LearningXNA4_lects/JesseSchell_playtesting101.pdf)):
- Expert gamers give "detailed comparisons with similar games" but don't represent the public; leaning on them can shrink your audience.
- One-time "tissue" testers bring fresh eyes, but relying on them gives "a good beginning that gets boring fast."
- Friends "don't want to hurt your feelings" and are "trying to like it."
- Every session needs set questions to answer.

Ubisoft Montreal selects testers from a survey of their play habits and asks them to play as they would at home ([Ubisoft](https://montreal.ubisoft.com/en/ubisoft-montreals-playtest-how-does-it-work-and-how-to-participate/)).

**Think-aloud and self-report.** Valve's GDC 2009 deck ([Ambinder](https://cdn.fastly.steamstatic.com/apps/valve/2009/GDC2009_ValvesApproachToPlaytesting.pdf)) says:
- Value "what people do—not what they say."
- Think-aloud can "create an artificial experience" and is "inaccurate and biased."
- Q&A suffers group biases and "potential for biased questions."
- Observers' presence can bias results.

Asking players to think aloud also lowers their sense of presence in the game ([Play-Aloud](https://igi-global.com/article/playing-aloud/296705)).

**Actionable feedback.**
- Microsoft's Pagulayan framed the job as finding the gap between what players actually experience and what the designer intended ([NPR](https://www.npr.org/transcripts/14649338)).
- RITE (Microsoft, tested on Age of Empires II's tutorial) fixes a problem as soon as it is seen and re-tests quickly ([Medlock et al.](https://jpattonassociates.com/wp-content/uploads/2015/04/rite_method.pdf)).
- Chris McDowall: "bring you problems, not solutions." Testers' fixes often pull against the game's vision ([Bastionland](https://www.bastionland.com/2022/08/mining-for-problems.html)).
- Schell Games warns that leading questions "suggest a 'correct' answer." Their neutral questions: most frustrating moment, favourite moment, anything you wanted to do but couldn't, how you'd describe the game to a friend ([Schell Games](https://schellgames.com/blog/the-definitive-guide-to-playtest-questions-for-video-game-playtesters)).
- Celia Hodent splits game UX into usability and "engage-ability" (motivation, emotion, game flow), a useful way to group report categories ([summary](https://www.designative.info/2019/03/28/the-ux-of-fortnite-celia-hodent/)).

**Severity and quitting.**
- NN/g rates severity from 0 (not a problem) to 4 (catastrophe) on frequency, impact and persistence. Evaluators rate independently, and the mean of three is enough in practice ([NN/g](https://www.nngroup.com/articles/how-to-rate-the-severity-of-usability-problems/)).
- PlaytestCloud asks "How often did you feel that you wanted to stop playing…?" and "If you were not in a playtest, do you think you would return…?" ([PlaytestCloud](https://help.playtestcloud.com/en/articles/6292169-survey-questions-for-examining-retention-in-your-playtest)).

## 2. Automated and LLM playtesting research

**Procedural personas.** Holmgård, Green, Liapis and Togelius define personas as utility functions an agent maximises ([IEEE ToG 2019](https://arxiv.org/abs/1802.06881)):
- Runner: reach the exit.
- Monster Killer: 0.7 × monsters slain + 0.3 × proximity to the exit.
- Treasure Collector and Completionist: the same shape for treasure and for everything collectable.

PathOS models player navigation with "a basic model of human behaviour," and developers found its predictions valuable while iterating ([Stahlke](https://ontariotechu.scholaris.ca/items/c5dc89c9-9d21-4140-bfbd-0d5ebb4b3472/full)). **(inference)** An LLM persona needs the same explicit statement of what it optimises and what it will trade away.

**LLM testers.**
- Agents' success at Wordle and Slay the Spire correlated strongly with how hard humans found the games, even with simple prompts ([Xiao & Yang 2024](https://arxiv.org/abs/2410.02829)).
- As models got closer to game-theoretic optimal play, their judgments fit human judgments worse ([Collins et al., ICLR 2026](https://arxiv.org/abs/2510.10930)). Some models are "hyper-accurate," giving exact answers where humans would guess ([Aher et al., ICML 2023](https://proceedings.mlr.press/v202/aher23a.html)).
- Frontier vision-language models barely progress in real-time games, and latency is a major limit ([VideoGameBench](https://arxiv.org/abs/2505.18134)). **(inference)** With batched input, the persona cannot genuinely judge pace or time pressure.
- PREFER rates on an anchored 1–10 scale, reports the median of three runs, subtracts each judge's habitual offset, and reports no human validation ([PREFER 2026](https://arxiv.org/abs/2610.19213)).

**How faithful simulated people are.**
- Silicon samples can match group averages ([Argyle et al.](https://arxiv.org/abs/2209.06899)), but their answers are more tightly clustered than real ones and many relationships fail to replicate ([Bisbee et al. 2024](https://www.cambridge.org/core/product/B92267DC26195C7F36E63EA04A47D2FE)).
- LLMs "misportray and flatten" identity groups ([Wang et al., Nature MI](https://arxiv.org/abs/2402.01908)).
- Persona variables explain under 10% of the variance in human annotations ([Hu & Collier, ACL 2024](https://aclanthology.org/2024.acl-long.554)).
- LLMs are poor at playing novices with incomplete knowledge ([Liu et al.](https://arxiv.org/abs/2310.02439)).
- Prompted agents predicted real shoppers' next actions only 11.86% of the time ([Lu et al.](https://arxiv.org/abs/2503.20749)).
- Researchers using UXAgent's simulated users found some behaviour "not what real users would do" ([UXAgent](https://arxiv.org/abs/2504.09407)).

**Sycophancy, drift and anchoring.**
- Social sycophancy, meaning excessive protection of the user's self-image, is rewarded in preference data and hard to mitigate ([ELEPHANT](https://arxiv.org/abs/2505.13995)).
- Instructions drift noticeably within eight rounds of dialogue ([Li et al., COLM 2024](https://arxiv.org/abs/2402.10962)).
- Persona drift can be measured three ways with an LLM judge: prompt-to-line, line-to-line and Q&A consistency ([Abdulhai et al., NeurIPS 2025](https://arxiv.org/abs/2511.00222)).
- LLM judges show position, verbosity and self-enhancement biases ([Zheng et al.](https://arxiv.org/abs/2306.05685)).
- Rubrics with per-score descriptors produced evaluations that correlate well with humans ([Prometheus](https://arxiv.org/abs/2310.08491)).

## 3. Recommendations for the loop

### 3.1 What goes in persona.md (about 600–900 words plus appendix; all inference unless cited)

1. **Identity in behaviour, not labels.** Age band, life situation, hardware, and when and how long they play. Leave out demographic labels that do nothing ([Wang](https://arxiv.org/abs/2402.01908)).
2. **Play history with named games and years.** For the veteran: WC3 TD maps such as Element TD and Gem TD, both from 2006 ([Wikipedia](https://en.wikipedia.org/wiki/Tower_defense)), and Legion TD's gold/lumber sends between two teams ([Wikipedia](https://en.wikipedia.org/wiki/Legion_TD)). Add what they play now.
3. **Motivation profile.** Rate the 12 Quantic Foundry motivations high, mid or low, with one sentence each on how it shows in play.
4. **Utility statement.** What they optimise, what they won't tolerate, what they'll trade away (Holmgård-style). For example: "maximise lives kept per gold; hates losing a 40-minute run to an unreadable wave."
5. **Skills and blind spots.** What they read and what they skim, their hotkey habits, mistakes they make under pressure. This counters optimiser play ([Collins](https://arxiv.org/abs/2510.10930), [Aher](https://proceedings.mlr.press/v202/aher23a.html)).
6. **Session habits and quit triggers.** "Leaves the lobby after 90 s of waiting," "alt-tabs during dead time."
7. **Voice.** Three to five real quotes in this player's register, with the source noted.
8. **Knowledge rules.** What they may know: on-screen information and their own diary, never the repo's docs. Flag "known only from the text description."
9. **Appendix of real material.** The owner's own long account of their WC3 TD years (the Park 2024 interview approach), plus curated real reviews and forum posts, negative ones included (the MeepleLM approach). Prefer this to LLM-written backstory ([Li et al.](https://arxiv.org/abs/2503.16527)).

### 3.2 The roster: four core personas plus rotating guests (inference)

| Persona | Mainly tests | Motivation lean | Main risk to manage |
|---|---|---|---|
| **The Veteran** (the base: WC3 TD 2004–2012, co-op TD with random teammates, now plays Legion TD 2) | High Water, Builders, balance, readability, expectations set by genre conventions | Strategy, Challenge, Completion high; Competition mid | Expert bias ([Schell](https://stewart.sdsu.edu/cs583_spr2013/LearningXNA4_lects/JesseSchell_playtesting101.pdf)); playing like an optimiser |
| **The Duelist** (ranked Legion TD 2, sends meta) | Undertow, Tide Race, fairness, counterplay, information | Competition, Strategy high | Overweighting the meta |
| **The Co-op Regular** (plays with a fixed friend group, sometimes the host) | Hub, party, queue, Ready, signals, roles, results | Community high, Challenge mid | Too polite |
| **The Fresh Tester** (newcomer to TD; played other genres) | First-time experience, tutorialisation, the Q W E / A S D card | Varies | LLMs can't really "not know" ([Liu](https://arxiv.org/abs/2310.02439)) |

- **Fresh Tester rules.** Retire the Fresh Tester after a few sessions and bring in a new one, because each tester is fresh only once. Weight its confusion reports heavily; when it reports no confusion, treat that as weak evidence.
- **Calibration critic.** Optionally run a skeptic now and then, drawn from real negative reviews of comparable TDs, as a probe for positivity bias.
- **Second model.** If you can, run at least one persona on a different model family ([Verga](https://arxiv.org/abs/2404.18796), [Play2Code](https://arxiv.org/abs/2605.28258)).
- **Disputed severity.** Ask three personas and take the mean ([NN/g](https://www.nngroup.com/articles/how-to-rate-the-severity-of-usability-problems/)).

### 3.3 Report format

```
Session card: persona, session #, mode/Builder/seed, party, time budget, mood
Timeline: key moments with frame ids
Problems (one row each):
  id | category (usability / engage-ability / balance / netcode / bug)
  severity 0-4 (NN/g) + frequency / persistence
  OBSERVATION: what was on screen and what I did (frames, inputs)
  INTERPRETATION: why I think it happened (hypothesis)
  IMPACT ON A PLAYER LIKE ME: what I'd do next (quit / work around / ignore)
  SUGGESTION (optional, clearly labelled, lowest priority)
  confidence | "known only from text description?" y/n
Highlights: also with frame evidence
Quit points: frame + reason; "times I wanted to stop" 1-5; "would return if not testing" 1-5
Could not judge: real-time feel, latency, audio, anything batching hid
Score 1-10 (anchored) + the one change that would raise it 1 point
Would keep playing / recommend: yes/no + the conditions
--- written only after the blind section ---
Patch-note verification: each note confirmed / not confirmed / not reached, with frames
Delta vs last session: shown only now, explain any change
Persona check: fixed answers
```

The labelled observation/interpretation/suggestion rows follow Valve, McDowall and Turpin. Frame anchoring follows Play2Code's "fully logged and traceable" feedback. Retrospective questions use Schell Games' neutral wording.

### 3.4 Keeping the persona honest (inference, built on the sources cited)

- **Anchored scale (draft).** Tie each score to behaviour, the way rubrics are given per-score descriptors ([Prometheus](https://arxiv.org/abs/2310.08491)):
  - 1: quit in the first match.
  - 3: one good idea buried under problems that would make me quit.
  - 4: tonight I'd go back to Legion TD 2.
  - 5: I'd finish this session but am not sure I'd launch it again this week.
  - 6: I'd play again if a friend asked.
  - 7: I'd start a session on my own and recommend it with caveats.
  - 8: my go-to TD for a while.
  - 9: I'd organise a group night around it.
  - 10: the best since WC3, nothing to fix before showing anyone.
- **Score ceiling.** 7 or above is allowed only with no open severity-3 or -4 problem.
- **Blind first.** The persona plays and writes before it sees patch notes or earlier scores ([Kapetanovic](https://arxiv.org/abs/2608.25869), [Sharma](https://arxiv.org/abs/2310.13548)). Write patch notes as a player-facing changelog, not as "please confirm we fixed X."
- **Optional separate scorer.** A second pass rates from the report alone; take the median of three ([PREFER](https://arxiv.org/abs/2610.19213)).
- **No negative quotas.** Quotas invite invented problems. Instead, if nothing reaches severity 2, the persona says so and lists what it tried.
- **Seeded canaries.** Occasionally plant a known defect or a deliberately unreadable wave and check whether it is reported. This measures detection rate and false positives.

### 3.5 Variation without losing continuity (inference)

- **Keep persona.md fixed.** Before each session, draw a session card: time budget, mood, party (solo, friends or strangers), a goal such as trying the Beekeeper or climbing, and a seed.
- **diary.md, after the generative-agents design** of memories plus periodic reflections ([Park et al. 2023](https://arxiv.org/abs/2304.03442)), holds:
  - game facts learned, so knowledge grows realistically;
  - open grievances with the session first seen and the frame;
  - expectations for the next build;
  - one paragraph of reflection.
- **Score ledger.** Keep scores outside the diary and out of context until the blind rating is done.
- **Re-read the persona** at the start of each match, given the drift within about eight rounds ([Li et al.](https://arxiv.org/abs/2402.10962)).

### 3.6 Detecting drift and sycophancy (inference)

- **Fixed persona-check questions** at the start and end of each session (history, pet peeves, what a 5 means), compared against persona.md. This is Q&A consistency ([Abdulhai](https://arxiv.org/abs/2511.00222)).
- **Separate auditor**, ideally another model family. It reads persona.md, the report and the frames, and flags:
  - claims with no frame;
  - knowledge the persona shouldn't have;
  - suggestions written as observations;
  - a score that contradicts the severity table.
- **Trend alarms:**
  - satisfaction rising while severity-3+ problems stay open;
  - every patch note "confirmed" without frames;
  - all personas converging on 7–9 ([MeepleLM](https://arxiv.org/html/2601.07251v1));
  - personas' wording converging toward each other ([Bisbee](https://www.cambridge.org/core/product/B92267DC26195C7F36E63EA04A47D2FE)).
- **Real-player check.** From time to time, compare the loop's findings with real playtests or with reviews of comparable games, and label the loop's output as synthetic ([NN/g](https://www.nngroup.com/articles/synthetic-users/)).

## 4. Gaps

- I found no study that validates LLM persona playtesters against human players of real-time games. MeepleLM and PREFER cover board and card games, and PREFER has no human study.
- Riot and Steve Swink turned up nothing citable on playtest method. Hodent's own wording on playtesting could not be verified beyond her framework. A widely quoted Neil Gaiman line on feedback could not be traced to a source, so I left it out.
- Quantic Foundry and PC Gamer pages blocked fetching. Those claims rest on search excerpts of the cited URLs.
