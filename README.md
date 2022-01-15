# schriftje

De kinderopvang van mijn kinderen maakt gebruik van een online systeem waarin de activiteiten te volgen zijn. Helaas heeft dit systeem geen notificatie functie. 
Dit stukje Python wordt via crontab ieder uur uitgevoerd (op de dagen dat ze naar de kinderopvang gaat). De code haalt de nieuwe berichten op en verstuurt deze via Signal naar mijn mobiele telefoon. 
Bijkomend voordeel is dat ook de foto's lokaal opgeslagen worden. Deze worden via een ander systeem in het fotoboek geplaatst.
