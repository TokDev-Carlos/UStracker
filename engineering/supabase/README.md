# Supabase — ambiente de engenharia preparado, não aplicado

O projeto Supabase atualmente conectado contém migrações/schemas de outro sistema. Por isso este handoff **não executa** SQL remoto.

Quando houver um projeto/branch dedicado ao UStracker, aplicar `migrations/0001_engineering_registry.sql` somente nesse ambiente. O schema `ustracker_eng` é privado e serve para registrar baselines, changesets, verificações, migrações, candidates e eventos de deployment; ele não substitui SQLCipher do produto desktop.

Regras:
- nunca usar `public` para esta camada;
- não conceder acesso a `anon`/`authenticated`;
- não armazenar dados pessoais ou dumps de `UserData`;
- hashes, IDs, resultados de testes e metadados técnicos são suficientes;
- qualquer criação de branch/projeto Supabase que possa gerar custo exige confirmação separada.
