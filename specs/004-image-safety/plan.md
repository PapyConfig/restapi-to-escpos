# Implementation Plan: Fin de job confirmée et images à la bonne taille

**Branch**: `004-image-safety` | **Date**: 2026-11-26 | **Spec**: [spec.md](spec.md)

## Summary

`transport.py` : lecteur continu des octets entrants (`_Incoming`), envoi de `GS r 1` après le
job, attente d'octets reçus après cette demande, puis FIN et attente de fermeture (inchangé).
`imaging.py` : réduction au lieu du refus. UI : `shrinkImage` / `fitSize` dans `preview.js`.

## Constitution Check

| Principe | Statut |
|---|---|
| I. Sécurité | ✅ aucune entrée client nouvelle |
| II. Contrat | ✅ inchangé (seule une erreur 422 « trop haute » disparaît) |
| III. Impression atomique | ✅ renforcée : le job suivant attend la fin réelle du précédent |
| IV. Tests sans matériel | ✅ imprimante factice qui répond à `GS r` ; tests d'ordre, de délai, d'état spontané |
| V. Simplicité | ✅ deux réglages, aucune dépendance |
