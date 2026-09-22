# 🧬 Proposta: Alias de Disciplinas (Mãe × Filha) — `aliases_id` + `aliases`

> Documento de referência. Implementa a unificação de disciplinas com sufixo
> (ex.: `PROGRAMAÇÃO WEB FRONT-END 2026A/2026B`) com a disciplina mãe
> (`PROGRAMAÇÃO WEB FRONT-END`), sem espalhar aliases pelo código.

---

## 1. Contexto / Diagnóstico

O portal (iSeduc) só conhece a disciplina **mãe** (sem sufixo) e é ela que aparece
em `historico_aulas`. Já as aulas (`lessons`) ficam sob a **filha** (com sufixo de
turma/período). Sem unificação, o plugin não acha o histórico da disciplina
selecionada e vice-versa.

Dados reais observados:

| id | nome | lessons | papel |
|----|------|---------|-------|
| 6 | PROGRAMAÇÃO WEB FRONT-END | 18 (órfãs) | **mãe/raiz** |
| 33 | PROGRAMAÇÃO WEB FRONT-END **2026A** | 45 | filha (turma 1) |
| 34 | PROGRAMAÇÃO WEB FRONT-END **2026B** | 42 | filha (turma 2) |
| 31 | PROGRAMAÇÃO WEB FRONT-END (…Turma I-B) | 0 | filha |
| 4 | PROGRAMAÇÃO ORIENTADA A OBJETOS - POO | — | **mãe/raiz** |
| 30 | …POO (…Turma I-A) | 41 | filha |

Referências por tabela:

| Tabela | Campo | Usa |
|--------|-------|-----|
| `class_subjects` | `subject_id` | filha |
| `lessons` | `subject_id` | **filha** |
| `historico_aulas` | `disciplina_id` (+`disciplina`) | **mãe/raiz** |
| `attendance` | `subject_id` | filha |
| `assessments` | `subject_id` | filha |
| `weekly_schedule` | `subject_name` (texto) | resolve por nome → raiz |

---

## 2. Modelo

Duas colunas em `subjects`:

| Campo | Papel |
|-------|-------|
| `aliases_id` (int, FK `subjects.id`) | Hierarquia filha → mãe. Suporta cadeia (mãe-filha): a resolução sobe até a raiz. |
| `aliases` (jsonb) | Nomes/apelidos que resolvem por texto (ex.: `["Web FE","2026A"]`). |

Regras:

- **Raiz** = `aliases_id IS NULL` → dona do `historico_aulas` e é o id/nome usado no TXT do plano.
- **Filha** = quem tem `lessons`.
- A mãe **não** deve ter aulas; as 18 lessons órfãs da mãe 6 são ignoradas pelo plugin.

---

## 3. DDL + Backfill + Funções

Ver arquivo `scripts/migracao_aliases_id_subjects.sql` (idempotente). Resumo:

```sql
ALTER TABLE subjects
  ADD COLUMN IF NOT EXISTS aliases_id integer REFERENCES subjects(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS aliases    jsonb NOT NULL DEFAULT '[]'::jsonb;

UPDATE subjects SET aliases_id = 6 WHERE id IN (33, 34, 31);
UPDATE subjects SET aliases_id = 4 WHERE id IN (30);

-- Funções: resolver_subject_raiz(id), resolver_subject_exato(nome), resolver_subject_id(nome)
```

---

## 4. Comportamento no código

### `services/database.py`

- **Novo** `get_subject_raiz(subject_id)`:
  1. RPC `resolver_subject_raiz` (se existir);
  2. fallback: caminha `aliases_id` no Python;
  3. fallback final: devolve o próprio id.
- `get_subject_by_name(name)`: mantém a ordem atual (exato → ilike) e **insere**
  o RPC `resolver_subject_exato` (nome/alias) **antes** do fuzzy. Só é chamado
  quando exato/ilike falham, então não há regressão de performance.

> Importante: `get_subject_by_name` continua devolvendo a **disciplina exata**
> (a filha quando o nome for da filha). Quem precisa da mãe usa `get_subject_raiz`.
> Isso evita que `seed_lessons.py` (que casa nome da pasta → disciplina) acabe
> gravando aulas na mãe.

### `data/repo/plugins/gerar_planos_txt.py`

Na seleção, calcula uma vez:

```python
id_filha = selected_subject['id']          # dona das lessons
id_mae   = resolver_raiz(id_filha)         # dona do historico_aulas
nome_mae = nome da raiz (sem sufixo)       # exibido/gravado no TXT
```

| Uso | Id |
|-----|-----|
| `buscar_historico_aulas` / `calcular_diagnostico` | **mãe** |
| `_lessons_light` / `_lessons_full_cached` / `auto_preencher_conteudo` | **filha** |
| `DISCIPLINA_ID` / `DISCIPLINA_NOME` no TXT e nome do arquivo | **mãe** |
| `verificar_plano_existente` / `_plano_pertence` (pastas prontas/pendentes) | **mãe** |
| `attendance` (frequência) | **filha** |
| Sugestão da grade semanal (`subject_name`) | `resolver_subject_id(nome)` → mãe |

Badge na Aba 1:
`PROGRAMAÇÃO WEB FRONT-END 2026A (id 33) → mãe PROGRAMAÇÃO WEB FRONT-END (id 6)`.

---

## 5. Rollout

1. Rodar `scripts/migracao_aliases_id_subjects.sql` no **SQL Editor do Supabase**.
2. Deploy do código (já resiliente: se o RPC não existir, usa fallback local).
3. Validar turma 1/33 e turma 2/34: diagnóstico lê histórico da mãe 6 e aulas da filha.
4. (Opcional) Popular `aliases` de outras disciplinas conforme necessidade.

---

## 6. Riscos

- `unaccent` pode não estar habilitado → funções usam fallback e o código mantém o `f_fuzzy_match`.
- Turma com mãe **e** filha em `class_subjects` → deduplicar por `id_mae` na UI.
- Planos antigos gerados com id da filha não serão encontrados por `_plano_pertence` (id_mae); renomear ou aceitar legado.
- Cadeias longas/ cíclicas: o walk tem limite de 10 níveis.
