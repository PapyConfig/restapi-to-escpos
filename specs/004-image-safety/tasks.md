# Tasks: Fin de job confirmée et images à la bonne taille

- [x] T001 `config.py` : `wait_done` (imprimante), `PRINTER_WAIT_DONE`, `PRINTER_DONE_TIMEOUT`, `MAX_IMAGE_HEIGHT` 2000
- [x] T002 Tests d'abord : ordre (le job suivant attend la confirmation), état spontané ignoré, pas de réponse → délai + avertissement, `wait_done=false` sans `GS r`
- [x] T003 `transport.py` : `_Incoming`, `_wait_done`, `_finish`
- [x] T004 `imaging.py` : réduction à la hauteur maximale + test
- [x] T005 UI : `fitSize`, `shrinkImage`, hauteur maximale dans l'aperçu + tests JS + test de cohérence avec le serveur
- [x] T006 Vérification navigateur : photo de 12 Mo → 576×768, 221 Ko, impression OK
- [x] T007 README, CHANGELOG 2.3.0, CLAUDE.md, `.env.example`, version
- [ ] T008 Validation sur l'imprimante réelle après déploiement (image puis mémo ; log `processed the job in`)
