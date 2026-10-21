# Mini CARE, in pairs: the Developer

Your Scientist partner creates the design and assigns you; open it from your list, then answer here.
Your partner's file: [`care-process-small-pair-scientist.md`](care-process-small-pair-scientist.md).

Sign up and open the design first: [`setup.md`](setup.md). Running alone? Use
[`care-process-small-solo.md`](care-process-small-solo.md).

Every participant gets the same 15 questions, in the same order. Write your own answers, or copy the ones
below. Your partner answers the same questions from their own file; the two sets differ a little on purpose,
and those differences are what you settle together in Reconcile.

- **It asks you to confirm or continue?** Reply `Yes.`
- **"Your answer is too vague"?** That is CARE pushing back. Add one concrete example, or paste your partner's answer.

---

## Open the design (Developer)

Sign up first, then give your Scientist the email you used: they create the design and assign you by that
email. When they have, open **Designs** and the design `Flood check agent` is there. Open its interview.

## Start the interview


Send this as the first message:

```
I want to design an agent that checks whether a place flooded, by comparing satellite images from before and after an event with TerraMind.
```

---

## Stage 1.1: Scope

**1. What is the purpose of the agent that is being designed?**

```
Run TerraMind on Sentinel-2 images of a named place for a before date and an after date, and report flood or no flood.
```

**2. Who are the primary users of the future agent? (roles only)**

```
Disaster analysts.
```

**3. What is their level of expertise?**

```
Comfortable reading satellite images; they do not write code.
```

**4. What tasks do these users expect the agent to support?**

```
Check one place and one before/after date pair at a time, and get the verdict with the scene ids.
```

**5. Walk me through the current step-by-step workflow for these tasks.**

```
Search a catalogue for scenes, download them, run a water index script on each, and compare the two maps.
```

**6. What are the main pain points or bottlenecks in this workflow?**

```
Every event needs new scripts and manual downloads; nothing is reused.
```

**7. Which decisions in this workflow must always remain human-controlled?**

```
Any alert or evacuation decision. The agent never sends an alert itself.
```

**8. How will users know the agent is successful? What does success look like?**

```
It returns flood or no flood, or cannot tell when an image is missing, with the water share before and after and the scene ids, in under 10 minutes. Test: Vlochos, Greece, September 2023 comes back as flood.
```

At the end of the stage it shows a summary and asks you to confirm:
```
Yes.
```

---

## Stage 2.3: Tools

**1. What actions need dedicated tools?**

```
geocode (place to area), pick_scene (clearest Sentinel-2 scene for a date), run_area (TerraMind over the area), compare_dates (before vs after).
```

**2. For the main tool, what are the exact inputs and outputs?**

```
run_area. In: scene id and area box. Out: land-cover shares including water %, scene date and cloud cover, job ids, and a map image.
```

**3. What errors are common, and what should the tool tell the agent when one occurs?**

```
No clear scene, area too big, or the TerraMind job failed. Retry once, then return the error so the agent answers cannot tell.
```

Confirm the stage:
```
Yes.
```

---

## Stage 3.1: Reasoning

**1. When the agent receives a typical request, how should it break the work into steps?**

```
geocode, then pick_scene for each date, run_area for each date, compare_dates, then report.
```

**2. When should the agent ask the user clarifying questions instead of guessing?**

```
When the place or dates are missing. It never guesses a date.
```

**3. How should the agent behave when it is unsure about an answer?**

```
Return cannot tell with the reason. Never call it a flood unless the radar check backs it.
```

**4. In what situations must the agent stop and escalate to a human?**

```
When it is asked about damage, casualties or forecasts, or to trigger an alert: it stops and says a human must decide.
```

Confirm the stage:
```
Yes.
```

---

## Stage 4.1: agents.md

No questions. When it asks whether to build `agents.md`:
```
Yes, build it.
```

---

---

## After Stage 4.1

Nothing more to answer. When your Scientist has run Reconcile and clicked **Publish**, your design is replaced
by the agreed one. If the interview asks you to continue, reply `Yes.`
