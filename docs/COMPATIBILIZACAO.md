# Processo de Compatibilização de Dados

## Contexto

O banco `escola_ativa.db` original tinha 21 tabelas com dados inconsistentes (FKs inválidas). Para não perder nenhum dado, criamos um processo em 3 fases:

```
escola_ativa_legado.db  ->  escola_ativa.db  ->  Supabase
(original completo)       (limpo, FK-valido)   (fonte de verdade)
```

## Fase 1: Backup (concluída)

- `escola_ativa_legado.db` (8.3MB) = cópia exata do original com TODOS os dados
- Nunca é sobrescrito
- Contém todos os 24,000+ registros incluindo os órfãos

## Fase 2: Limpeza (concluída)

- `data/prepare_clean_db.py` cria `escola_ativa.db` filtrando registros com FK inválida
- Resultado: 1,657 registros válidos de 11 tabelas
- 1,018 registros órfãos ficam preservados no legado

## Fase 3: Compatibilização (pendente)

### Objetivo
Restaurar todos os dados do legado para um banco funcional com FKs válidas.

### Fontes de dados órfãos

| Tabela | Registros órfãos | Causa provável |
|--------|-----------------|----------------|
| `quiz_questions` | 973 | `quiz_id` não existe em `quizzes` |
| `student_assessments` | 45 | `assessment_id` não existe em `assessments` |
| `weekly_schedule` | 0 | `class_id` não existe em `classes` |
| `attendance` | 0 | `subject_id`/`class_id` não existem |

### Processo de Compatibilização

```python
# data/compatibilizar.py (conceitual)

# 1. Abrir o banco legado
LEGACY = "data/escola_ativa_legado.db"

# 2. Para cada tabela órfã, identificar a causa
#    ex: quiz_questions com quiz_id que não existe em quizzes

# 3. Opção A: Criar registros "placeholder" para conectar órfãos
#    CREATE TABLE IF NOT EXISTS lessons (id, title, ...)
#    Inserir disciplinas/aulas que faltam com dados mínimos

# 4. Opção B: Reconstruir FKs com base em nomes/contexto
#    Se quiz_questions tem quiz_id=529 mas quizzes não tem id=529,
#    procurar o quiz pelo contexto (lesson_id, title) e corrigir

# 5. Migrar para escola_ativa_compat.db
#    Banco final com TODOS os dados e FKs válidas

# 6. Atualizar Supabase
#    sync.py lê do compat.db e envia para Supabase
```

### Estratégia de Reparação

**Para quiz_questions (973 órfãos):**
1. Cruzar `quiz_questions.quiz_id` com `quizzes.lesson_id` e `quizzes.title`
2. Se o quiz não existe, criar uma entrada `quizzes` com dados mínimos
3. Atualizar `quiz_questions.quiz_id` para o ID correto

**Para student_assessments (45 órfãos):**
1. Cruzar `student_assessments.assessment_id` com `assessments`
2. Se a avaliação não existe, verificar se existe no `escola_ativa_legado`
3. Criar a avaliação faltante ou corrigir o ID

### Por que 18 tabelas e por que não se pode perder dados órfãos

O schema final tem 18 tabelas porque cada uma tem responsabilidade única e não pode ser fundida sem quebrar a normalização. Fusão implicaria dados duplicados ou NULLs — exatamente o problema do banco legado.

| # | Tabela | Por que separada? |
|---|--------|-------------------|
| 1 | `users` | Auth (username, role, password_hash) |
| 2 | `classes` | Entidade raiz da organização |
| 3 | `subjects` | Metadados próprios (aliases, carga_horaria, type) |
| 4 | `class_subjects` | Relação N:N turma↔disciplina |
| 5 | `student_enrollments` | Matrículas ≠ class_subjects |
| 6 | `lessons` | Conteúdo pedagógico completo |
| 7 | `quizzes` | Metadados do quiz |
| 8 | `quiz_questions` | Questões são JSON complexo |
| 9 | `assessments` | MN1/MN2/MN3 têm lógica própria |
| 10 | `assessment_questions` | JSON complexo |
| 11 | `student_assessments` | Submissões com score/status |
| 12 | `student_assessment_answers` | Respostas individuais por questão |
| 13 | `attendance` | Frequência com campos específicos |
| 14 | `forum_posts` | Conteúdo de fórum |
| 15 | `weekly_schedule` | Grade horária |
| 16 | `user_history` | Audit trail (13,547 registros) para cálculo de progresso e notas |
| 17 | `qualitative_points` | Notas descritivas ≠ notas quantitativas |
| 18 | `student_grades` | Notas calculadas automáticas |

**Consequência de perder dados órfãos:** Sem `quiz_questions` e `student_assessments` completos, o `user_history` e `student_grades` não podem ser calculados corretamente. O aluno perde histórico de progresso, notas e atividades. Cada registro órfão é um pedaço do histórico escolar de um aluno real.

### Scripts Necessários

- `data/compatibilizar.py` — script principal de compatibilização
- `data/verificar_orphans.py` — relatório de órfãos detalhado
- `data/restore_orphans.py` — restaura órfãos no banco compatível

### Ordem de Execução

```bash
# 1. Gerar relatório de órfãos
python data/verificar_orphans.py

# 2. Executar compatibilização
python data/compatibilizar.py

# 3. Verificar resultado
python data/prepare_clean_db.py  # agora lê do compat

# 4. Enviar para Supabase
python data/migrate.py
```

### Resultado Final Esperado

| Tabela | Registros |
|--------|-----------|
| users | 46 |
| classes | 2 |
| subjects | 16 |
| class_subjects | 28 |
| student_enrollments | 42 |
| lessons | 357 |
| quizzes | 338+ |
| quiz_questions | 973 |
| assessments | 15 |
| assessment_questions | 135 |
| student_assessments | 388 |
| student_assessment_answers | 3,167 |
| attendance | 488 |
| forum_posts | 3,669 |
| weekly_schedule | 22 |
| user_history | 13,547 |
| **Total** | **~24,000** |
| user_history | 13,547 | legado histórico de aulas |

## Notas Importantes

1. **Nunca sobrescrever `escola_ativa_legado.db`**
2. **Sempre manter `escola_ativa.db` como referência limpa**
3. **`escola_ativa_compat.db` será o banco final de produção**
4. **O Supabase recebe dados do `escola_ativa.db` (ou `compat.db`)**
5. **O `user_history` (13,547 registros) é crítico para cálculo de notas**
