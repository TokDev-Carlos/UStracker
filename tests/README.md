# tests

```bash
export PYTHONPATH=src:. USTRACKER_DEV_PLAINTEXT=1
python -m unittest discover -s tests -p 'test_*.py'   # backend, rotas, nuvem (simulador), permissões
node --test tests/*.test.mjs                           # telas
```
Prefixos: `r*` base, `aj*` ajustes, `c*` nuvem, `u*` usuários, `s*` Servidores, `n*` placa, `v*` frotas, `g*` Release 2.
Testes de nuvem precisam do Node (sobem `cloud/harness/gas_server.mjs`).
