# Cronjob za dnevno poročilo k3s

## Kreiran job
- job_id: 329de8296a66
- name: cluster-daily-report
- schedule: vsak dan ob 04:00
- script: ~/.hermes/scripts/cluster_report.py
- env file: ~/.hermes/scripts/.cluster_mail.env
  - REPORT_EMAIL=matej.cusin2@guest.arnes.si
  - MAIL_FROM, MAIL_USERNAME, MAIL_PASSWORD, MAIL_SERVER, MAIL_PORT — SMTP Arnes

## Kako deluje
Script s kubectl pobere stanje (workerji, masterji, Longhorn, replike, appi) in pošlje na email preko Arnesovega SMTP. Cronjob način: no_agent=true, ker script kar sam email pošlje.

## Test
Ob 04:49 je bil poslan testni email na matej.cusin2@guest.arnes.si ✅
Cronjob je bil tudi sprožen z action=run.

## Spremenljivka v -env
V .cluster_mail.env je REPORT_EMAIL=matej.cusin2@guest.arnes.si — to je enostavno menjati, če želiš drug naslov.
