# 📄 Documentação Atualizada: Plugin Gerar Planos de Aula

## Comparativo: class_registry.py vs gerar_planos_txt.py

| Aspecto | class_registry.py | gerar_planos_txt.py |
|---------|-------------------|---------------------|
| **Cálculo de aula** | Usa `historico_aulas` do banco (preciso) | Usa seleção manual ou regex no título |
| **Preenchimento** | Smart-Fill automático (título + introdução) | Extração parcial via regex |
| **Integração curricular** | BNCC/EPT (competências, habilidades) | Não integrado |
| **Detecção de duplicatas** | Verifica `historico_aulas` antes de salvar | Não verifica |
| **Mapeamento de disciplinas** | `mapping_grade_to_db` (apelidos → nomes reais) | Fuzzy matching frágil |
| **Cálculo de carga horária** | Limite proporcional (400h / num_subjects) | Não calcula |
| **Passos** | 4 passos claros | 1 tela complexa com muitos campos |

---

## Lições do class_registry.py para o gerar_planos

### 1. Cálculo Automático do Número da Aula

O `class_registry.py` resolveu o problema do "número da aula" consultando o `historico_aulas`:

```python
# class_registry.py linha 331-337
hist_count = db.supabase.table("historico_aulas")\
    .select("*", count='exact')\
    .eq("disciplina_id", sub_id)\
    .execute()

n_aula = (hist_count.count if hist_count.count is not None else 0) + 1
```

**Para o gerar_planos:** Usar a mesma lógica para sugerir automaticamente o número da aula, em vez de exigir que o professor selecione manualmente.

### 2. Smart-Fill de Conteúdo

O `class_registry.py` busca título + introdução automaticamente:

```python
# class_registry.py linha 79-83
title_match = re.search(r'^#\s+(.*)', content, re.MULTILINE)
title = title_match.group(1).strip() if title_match else lesson_file.replace(".md", "")

intro_match = re.search(r'##\s+(?:🏁\s+)?Introdução\n+(.*?)\n(?:#|---)', content, re.DOTALL | re.IGNORECASE)
intro = intro_match.group(1).strip() if intro_match else "Conteúdo da aula teórica e prática."
```

**Para o gerar_planos:** Extrair não só título e introdução, mas também objetivos, atividade e recursos de forma mais robusta.

### 3. Mapeamento de Disciplinas

O `class_registry.py` usa um dicionário explícito:

```python
# class_registry.py linha 205-209
mapping_grade_to_db = {
    "P.C. II": "PENSAMENTO COMPUTACIONAL II",
    "Ment.Tec.II": "MENTORIAS TEC II",
    "I.A.": "INTELIGÊNCIA ARTIFICIAL"
}
```

**Para o gerar_planos:** Criar mapeamento similar para evitar fuzzy matching frágil.

### 4. Verificação de Duplicatas

O `class_registry.py` verifica se já existe registro para aquela data/disciplina:

```python
# class_registry.py linha 321-328
exist_res = db.supabase.table("historico_aulas")\
    .select("id, status")\
    .eq("data_aula", dt_str)\
    .eq("disciplina_id", sub_id)\
    .execute()

if exist_res.data:
    st.warning(f"⚠️ Já existe registro oficial para esta data no iSeduc.")
```

**Para o gerar_planos:** Verificar se já existe plano gerado para aquela turma/disciplina/aula antes de gerar um novo.

### 5. Limite de Carga Horária

```python
# class_registry.py linha 307-308
num_subjects = len(subjects_db) if (subjects_db and len(subjects_db) > 0) else 10
limit_lessons = 400 // num_subjects
```

**Para o gerar_planos:** Calcular automaticamente quantas aulas podem ser geradas para cada disciplina.

---

## Estrutura Proposta: gerar_planos v2

### Fluxo Otimizado (4 passos)

```
┌─────────────────────────────────────────────────────────────┐
│  PASSO 1: CONTEXTO                                          │
│  ├── Turma (auto-selecionada se única)                      │
│  ├── Data da Aula                                           │
│  └── Horário (auto-sugerido pela grade)                     │
├─────────────────────────────────────────────────────────────┤
│  PASSO 2: DISCIPLINA E AULA                                 │
│  ├── Disciplina (auto-sugerida pela grade no dia/horário)   │
│  ├── Número da Aula (calculado do historico_aulas)          │
│  └── Detecção de plano existente                            │
├─────────────────────────────────────────────────────────────┤
│  PASSO 3: CONTEÚDO (auto-preenchido)                        │
│  ├── Título (do .md ou banco)                               │
│  ├── Objetivos (do .md ou banco)                            │
│  ├── Atividade (do .md ou banco)                            │
│  ├── Recursos (do .md ou banco)                             │
│  └── Estratégia (seleção)                                   │
├─────────────────────────────────────────────────────────────┤
│  PASSO 4: FREQUÊNCIA E CONFIRMAÇÃO                          │
│  ├── Lista de presença (auto-carregada)                     │
│  ├── Revisão final                                          │
│  └── Gerar / Salvar / Download                              │
└─────────────────────────────────────────────────────────────┘
```

### Funções-Chave a Implementar

#### 1. `calcular_n_aula_automatico()`

```python
def calcular_n_aula_automatico(disciplina_id: int, data_str: str) -> int:
    """Calcula o número da aula baseado no histórico de registros."""
    if not db or not db.is_db_connected():
        return 1
    
    try:
        # Conta registros existentes no historico_aulas
        hist_count = db.supabase.table("historico_aulas")\
            .select("*", count='exact')\
            .eq("disciplina_id", disciplina_id)\
            .execute()
        
        return (hist_count.count or 0) + 1
    except:
        return 1
```

#### 2. `auto_preencher_conteudo()`

```python
def auto_preencher_conteudo(turma_nome: str, disciplina_nome: str, aula_num: int) -> dict:
    """Preenche automaticamente título, objetivos, atividade e recursos."""
    
    # 1. Busca no catálogo de arquivos .md
    dados_md = extrair_dados_aula_md(turma_nome, disciplina_nome, aula_num)
    
    # 2. Busca no banco de dados
    lesson_db = None
    if db and db.is_db_connected():
        subjects = db.get_subjects_for_class(...)
        for s in subjects:
            lessons = db.get_lessons_for_subject(s['id'])
            for l in lessons:
                if re.search(rf"Aula\s*0?{aula_num}\b", l['title'], re.IGNORECASE):
                    lesson_db = l
                    break
    
    # 3. Prioriza banco > .md > fallback
    titulo = (lesson_db or {}).get('title') or dados_md.get('title') or f"Aula {aula_num:02d}"
    objetivos = (lesson_db or {}).get('objective') or extrair_objetivos(dados_md.get('content', ''))
    atividade = extrair_atividade(dados_md.get('content', ''))
    recursos = (lesson_db or {}).get('resources') or extrair_recursos(dados_md.get('content', ''), titulo)
    
    return {
        'titulo': titulo,
        'objetivos': objetivos,
        'atividade': atividade,
        'recursos': recursos,
        'fonte': 'banco' if lesson_db else ('arquivo' if dados_md.get('found') else 'padrao')
    }
```

#### 3. `verificar_plano_existente()`

```python
def verificar_plano_existente(turma_id: int, disciplina_id: int, aula_num: int) -> dict:
    """Verifica se já existe plano gerado para esta aula."""
    nome_arquivo = f"PLANO_TURMA_{turma_id}_DISC_{disciplina_id}_AULA_{aula_num:02d}.txt"
    caminho = os.path.join(OUTPUT_DIR_REPO, nome_arquivo)
    
    if os.path.exists(caminho):
        with open(caminho, 'r', encoding='utf-8') as f:
            conteudo = f.read()
        
        match_data = re.search(r'DATA:\s*(\d{4}-\d{2}-\d{2})', conteudo)
        return {
            'existe': True,
            'data': match_data.group(1) if match_data else "desconhecida",
            'caminho': caminho
        }
    
    return {'existe': False}
```

#### 4. `calcular_datas_sequenciais()`

```python
def calcular_datas_sequenciais(turma_id: int, disciplina_id: int, data_inicio: date, num_aulas: int) -> list:
    """Calcula datas sequenciais baseado na grade semanal."""
    # Busca os dias que a disciplina tem aula
    grade = carregar_grade_semanal()
    turma_nome = obter_nome_turma(turma_id)
    
    dias_disciplina = set()
    for dia, horarios in grade.get(turma_nome, {}).items():
        for horario, disc in horarios.items():
            if disciplina_nome.upper() in disc.upper():
                dias_disciplina.add(dia)
    
    datas = []
    data_atual = data_inicio
    
    while len(datas) < num_aulas:
        dia_semana = obter_nome_dia(data_atual.weekday())
        if dia_semana in dias_disciplina:
            datas.append(data_atual)
        data_atual += timedelta(days=1)
    
    return datas
```

---

## Checklist de Implementação (Priorizado)

### Fase 1: Auto-preenchimento Inteligente (1 semana)
- [ ] Implementar `calcular_n_aula_automatico()` usando `historico_aulas`
- [ ] Implementar `auto_preencher_conteudo()` com prioridade banco > .md > fallback
- [ ] Implementar `verificar_plano_existente()`
- [ ] Modificar `render()` para usar auto-preenchimento
- [ ] Adicionar indicador de fonte dos dados (banco/arquivo/padrão)

### Fase 2: Grade Inteligente (1 semana)
- [ ] Implementar `calcular_datas_sequenciais()` para geração em lote
- [ ] Auto-sugerir disciplina baseado na grade no dia/horário
- [ ] Adicionar mapeamento explícito de disciplinas (como `class_registry.py`)
- [ ] Mostrar conflitos (plano já existe para aquela data)

### Fase 3: Integração com Portal (2 semanas)
- [ ] Integrar com `historico_aulas` para verificação de duplicatas
- [ ] Adicionar campos de currículo (BNCC/EPT) se necessário
- [ ] Sincronizar planos gerados com o histórico do portal

### Fase 4: Geração em Lote Aprimorada (1 semana)
- [ ] Gerar planos para semana inteira com datas corretas
- [ ] Preview de todos os planos antes de salvar
- [ ] Exportação em lote (ZIP com todos os .txt)

---

## Métricas de Sucesso

| Métrica | Antes | Depois (meta) |
|---------|-------|---------------|
| Tempo por plano | ~3 min | ~30 seg |
| Cliques necessários | ~15 | ~5 |
| Campos manuais | ~8 | ~2 |
| Erros de número de aula | Comum | Eliminado |
| Planos duplicados | Possível | Bloqueado |
