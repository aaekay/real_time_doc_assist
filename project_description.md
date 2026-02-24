# Project Description (Main Track Write-up Draft)

### Project Name
OPD Question Copilot

### Problem Statement
Outpatient consultations are high-volume and time-constrained, which often leads to incomplete history-taking, inconsistent follow-up questioning, and missed red-flag symptoms. These gaps affect care quality, referral timing, and documentation quality, especially in settings where clinicians must make fast decisions across diverse cases. Existing tools usually help after the visit (documentation) rather than during the live interview, when clinical context is still being gathered.

OPD Question Copilot addresses this unmet need by providing real-time interview support while the doctor-patient conversation is happening. The goal is to improve consultation completeness and safety without replacing physician judgment.

### Overall Solution
Our system is an end-to-end, real-time assistant that combines two Google HAI-DEF models:

1. MedASR (`google/medasr`) for medical-domain speech transcription from live audio.
2. MedGemma (`google/medgemma-4b-it`) for clinical reasoning tasks that operate on the transcript and encounter state.

MedGemma is used in a multi-role orchestration pipeline rather than a single prompt flow. It performs:

1. Structured clinical extraction (symptoms, history, red flags, context).
2. Priority-ranked next-best question generation.
3. Consult/referral specialty and urgency suggestion.
4. Safety filtering of generated questions.
5. End-of-visit SOAP-style summary generation.

This design demonstrates effective HAI-DEF utilization by mapping model capabilities directly to practical clinical workflow steps.

### Technical Details
Architecture: browser microphone streaming over WebSocket to a FastAPI backend, with low-latency incremental processing and a React frontend for live guidance panels.

Key implementation characteristics:

1. Real-time streaming pipeline: live audio chunks are transcribed and continuously processed.
2. Session-scoped state: encounter context is accumulated in memory for coherent multi-turn reasoning.
3. Parallel MedGemma tasks: question generation and consult reasoning run with controlled concurrency.
4. Safety boundary: generated prompts are filtered for appropriateness before display.
5. Reproducible evaluation: scripted benchmark on diverse synthetic vignettes (e.g., cardiology, pediatrics, neurology, respiratory, psychiatry, dermatology, ENT, GI, orthopedics, endocrine).

This makes the project feasible as a deployable product prototype, not only a benchmark demo.

### Impact Potential
If deployed in OPD workflows, the system can improve care quality through more consistent interview depth, stronger red-flag coverage, and better referral timing. It is particularly relevant in privacy-sensitive or infrastructure-constrained environments because it uses open-weight healthcare models with controllable deployment architecture.

Expected outcome areas:

1. Better history completeness and question relevance during visits.
2. Reduced variability across clinician interviews.
3. Faster, more structured post-visit documentation support.
4. Improved consistency in identifying cases that may require specialist escalation.

In summary, OPD Question Copilot translates HAI-DEF model capabilities into a clinically meaningful, technically feasible, and workflow-integrated Main Track application.
