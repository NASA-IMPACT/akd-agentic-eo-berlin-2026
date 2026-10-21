# Mini CARE, in pairs: the Scientist (lead)

You create the design and assign your Developer partner, you both answer, and you run Reconcile at the end.
Your partner's file: [`care-process-small-pair-developer.md`](care-process-small-pair-developer.md).

Sign up and open the design first: [`setup.md`](setup.md). Running alone? Use
[`care-process-small-solo.md`](care-process-small-solo.md).

Every participant gets the same 15 questions, in the same order. Write your own answers, or copy the ones
below. Your partner answers the same questions from their own file; the two sets differ a little on purpose,
and those differences are what you settle together in Reconcile.

- **It asks you to confirm or continue?** Reply `Yes.`
- **"Your answer is too vague"?** That is CARE pushing back. Add one concrete example, or paste your partner's answer.

---

## Create the design (Scientist)

**Designs → New design**, from the workshop template:

| Field | Value |
| --- | --- |
| Name | `Flood check agent` |
| Description | `Checks whether a named place flooded between two dates, with TerraMind over Sentinel-2, and reports the evidence.` |
| Model | `DeepSeek-V4.1-Flash (fast, HZDR)`. If it is already selected, leave it. |

Then, in the design header, **assign** your Developer by their email. They must have signed up first, or
they will not be in the list; ask them for the email they used.

## Start the interview


Send this as the first message:

```
I want to design an agent that checks whether a place flooded, by comparing satellite images from before and after an event with TerraMind.
```

---

## Stage 1.1: Scope

**1. What is the purpose of the agent that is being designed?**

```
Tell an analyst whether a named place flooded, by comparing a date before and a date after an event, with the satellite evidence behind the answer.
```

**2. Who are the primary users of the future agent? (roles only)**

```
Disaster analysts and Earth scientists.
```

**3. What is their level of expertise?**

```
Experts in remote sensing and floods, not in machine learning.
```

**4. What tasks do these users expect the agent to support?**

```
Check whether a reported flood happened at a place, and see the images that show it.
```

**5. Walk me through the current step-by-step workflow for these tasks.**

```
Search for clear images before and after by hand, download them, compare the water by eye or with a threshold, then write it up.
```

**6. What are the main pain points or bottlenecks in this workflow?**

```
Finding cloud-free images and comparing them takes hours for every event.
```

**7. Which decisions in this workflow must always remain human-controlled?**

```
Issuing flood alerts and ordering evacuations. The agent only informs them.
```

**8. How will users know the agent is successful? What does success look like?**

```
It answers flood, no flood or cannot tell (when there is no clear image, or the radar does not back the water), and shows the images and dates it used. Test: Conselice, Italy, May 2023 comes back as flood; the same place a month earlier comes back as no flood.
```

At the end of the stage it shows a summary and asks you to confirm:
```
Yes.
```

---

## Stage 2.3: Tools

**1. What actions need dedicated tools?**

```
Finding the place, finding a clear image before and after the date, and checking for water.
```

**2. For the main tool, what are the exact inputs and outputs?**

```
In: the area and two dates. Out: flood or no flood, how much of the area is water before and after, and the images.
```

**3. What errors are common, and what should the tool tell the agent when one occurs?**

```
Too cloudy, or no image near the date. Say which date could not be checked, and never switch to a different place or date.
```

Confirm the stage:
```
Yes.
```

---

## Stage 3.1: Reasoning

**1. When the agent receives a typical request, how should it break the work into steps?**

```
Find the place, get a clear image before and after the date, run TerraMind on both, compare the water, then report with the images.
```

**2. When should the agent ask the user clarifying questions instead of guessing?**

```
When the place or the dates are missing, or the place name matches more than one place.
```

**3. How should the agent behave when it is unsure about an answer?**

```
Say cannot tell, why (cloud, no image, radar disagrees), and what would settle it.
```

**4. In what situations must the agent stop and escalate to a human?**

```
When someone asks it to decide on an alert or an evacuation: it stops and hands that to a human analyst.
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

## Reconcile (Scientist / lead only)

When you have both finished 4.1, open **Reconcile**, select both of you as sources, and send:
```
Reconcile our two designs.
```
Read the differences it found, then reply:
```
Go with your recommendations, leave the rest open, and bring agents.md across.
```
Then click **Publish**. Both of you now have the same agreed design.

