# Break IT up, or not!

For et stykke tid siden delte jeg en tegning her: en trekvist tegnet i hånden — bare
streger og prikker på et stykke papir. Tre AI'er, samme prompt:

*"Jeg kunne godt tænke mig en simpel og symmetrisk SVG af denne tegning"*

Ingen af dem ramte den. Streger der ikke mødtes, forkert antal prikker, proportioner
der driftede.

Så prøvede jeg det oplagte: at bryde opgaven op.

Jeg tegnede figuren forfra i to lag — den afrundede trekant på ét ark, knuden med de
tre løkker på et andet — og gav dem til modellen hver for sig.

Det virkede. Kimi K3 nåede i mål efter en række prompts. Første gang en model faktisk
landede figuren. Kineserne er godt på vej.

Men så prøvede jeg det modsatte: samme originale billede, ingen opdeling, én prompt.
Bare en model der kan bruge værktøjer — Claude Opus 5 i Claude Code.

Den croppede selv fotoet og zoomede ind på krydsningerne. Læste figuren som to lag:
en trefolieknude og en afrundet trekant, drejet 60° i forhold til hinanden. Fandt de
seks prikker — tre i løkkernes centre, tre inde i trekantens hjørner. Udledte hele
geometrien af to radier. Renderede så sit eget SVG til PNG, kiggede på billedet,
justerede, renderede igen.

Fire runder, 15 varianter. Så var den der. Én prompt, ingen opdeling.

Og her er pointen, som jeg ikke havde set komme:

**Det handlede aldrig om at bryde billedet op. Det handlede om at bryde arbejdet op —
og om at modellen kan se sit eget resultat.**

Claude fejlede også i runde ét. Samme familie, samme øjne. Forskellen var ikke synet.
Forskellen var loopet: render → kig → ret.

En chat gætter én gang. En agent kan tjekke sig selv.

Så svaret på mit eget spørgsmål fra sidste opslag — *"er der en prompt-teknik til at få
en model til at se et billede mere præcist?"* — er vist:

Giv den øjne på sit eget output i stedet for en bedre beskrivelse af inputtet.

Break it up? Nogle gange. Men luk hellere loopet.

*(Fuld åbenhed: dette opslag er skrevet sammen med den agent, der løste opgaven.
Gør med den viden hvad I vil.)*

#AI #PromptEngineering #Hallucinations #GenerativeAI #AgenticAI
