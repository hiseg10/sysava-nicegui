# 🎯 Plano de Melhorias: gerar_planos_txt.py (v2)

## Diagnóstico: Por que o plugin é pouco atrativo?

### Problemas Identificados

1. **Muito preenchimento manual** - O professor precisa selecionar número da aula, título, objetivos, atividade, recursos... tudo manualmente.

2. **Número da aula impreciso** - Usa regex no título ou entrada manual, gerando erros (ex: "Aula 114").

3. **Sem detecção de duplicatas** - Pode gerar planos duplicados sem aviso.

4. **Sem integração com portal** - Não verifica o que já foi registrado no iSeduc.

5. **Geração em lote defeituosa** - Todos os planos recebem a mesma data.

6. **Interface sobrecarregada** - Uma tela com muitos campos ao invés de passos claros.

---

## Solução: Aprender com class_registry.py

O `class_registry.py` já resolveu vários desses problemas:

| Problema | Solução no class_registry | Aplicação no gerar_planos |
|----------|---------------------------|---------------------------|
| Número da aula | Consulta `historico_aulas` | Usar mesma lógica |
| Preenchimento | Smart-Fill de .md | Expandir para objetivos/atividade/recursos |
| Duplicatas | Verifica antes de salvar | Verificar plano existente |
| Interface | 4 passos claros | Reestruturar em 4 passos |
| Carga horária | Limite proporcional | Calcular automaticamente |

---

## Visão do Futuro: gerar_planos v2

### Conceito: **Planejador Inteligente com 4 Passos**

```
PASSO 1: CONTEXTO (2 campos)
  → Turma + Data
  → Auto-sugere: horário, disciplina, número da aula

PASSO 2: REVISÃO (3 campos)
  → Disciplina confirmada
  → Número da aula calculado
  → Alerta se plano já existe

PASSO 3: CONTEÚDO (auto-preenchido)
  → Título (do .md ou banco)
  → Objetivos (do .md ou banco)
  → Atividade (do .md ou banco)
  → Recursos (do .md ou banco)
  → Estratégia (seleção)

PASSO 4: FREQUÊNCIA + CONFIRMAÇÃO
  → Lista de presença (auto-carregada)
  → Preview do plano
  → Botões: Salvar / Download / Gerar Lote
```

---

## Fases de Implementação

### Fase 1: Auto-preenchimento Inteligente (MVP)
**Tempo estimado:** 1 semana  
**Impacto:** Alto  
**Esforço:** Baixo

| Item | Descrição |
|------|-----------|
| `calcular_n_aula_automatico()` | Usa `historico_aulas` para calcular número correto |
| `auto_preencher_conteudo()` | Busca título, objetivos, atividade e recursos automaticamente |
| `verificar_plano_existente()` | Alerta se já existe plano para aquela aula |
| Indicador de fonte | Mostra se dados vieram do banco, .md ou são padrão |

### Fase 2: Grade Inteligente
**Tempo estimado:** 1 semana  
**Impacto:** Alto  
**Esforço:** Médio

| Item | Descrição |
|------|-----------|
| Auto-sugestão de disciplina | Usa grade semanal para sugerir disciplina no dia/horário |
| Mapeamento explícito | Dicionário de apelidos (como `class_registry.py`) |
| `calcular_datas_sequenciais()` | Calcula datas corretas para geração em lote |
| Detecção de conflitos | Verifica se há sobreposição de planos |

### Fase 3: Geração em Lote Aprimorada
**Tempo estimado:** 1 semana  
**Impacto:** Médio  
**Esforço:** Médio

| Item | Descrição |
|------|-----------|
| Gerar semana inteira | Gera planos para todos os dias da semana com datas corretas |
| Preview em lote | Mostra todos os planos antes de salvar |
| Exportação ZIP | Baixa todos os planos de uma vez |

### Fase 4: Integração com Portal
**Tempo estimado:** 2 semanas  
**Impacto:** Alto  
**Esforço:** Alto

| Item | Descrição |
|------|-----------|
| Verificação de duplicatas | Consulta `historico_aulas` antes de gerar |
| Sincronização | Marca planos que já foram registrados no portal |
| Campos de currículo | Adiciona competências/habilidades se necessário |

---

## Arquitetura Proposta

```
┌─────────────────────────────────────────────────────────────────┐
│                    GERAR PLANOS v2                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────┐    │
│  │  CONTEXTO    │    │   GRADE      │    │   HISTÓRICO     │    │
│  │  Turma+Data  │◄──►│   SEMANAL    │───►│   iSeduc        │    │
│  └──────┬──────┘    └──────┬───────┘    └────────┬────────┘    │
│         │                  │                      │             │
│         ▼                  ▼                      ▼             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              MOTOR DE INTELIGÊNCIA                       │   │
│  │  • calcular_n_aula_automatico()                         │   │
│  │  • auto_preencher_conteudo()                            │   │
│  │  • verificar_plano_existente()                          │   │
│  │  • calcular_datas_sequenciais()                         │   │
│  │  • mapear_disciplina()                                  │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              GERADOR DE SAÍDA                            │   │
│  │  • TXT (atual)                                          │   │
│  │  • Preview formatado                                    │   │
│  │  • Download individual ou ZIP                           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Código Base para Implementação

### 1. Mapeamento de Disciplinas

```python
# Adicionar no topo do arquivo
MAPPING_DISCIPLINAS = {
    "P.C. II": "PENSAMENTO COMPUTACIONAL II",
    "P.C.II": "PENSAMENTO COMPUTACIONAL II",
    "Ment.Tec.II": "MENTORIAS TEC II",
    "MENTORIAS TEC II": "MENTORIAS TEC II",
    "I.A.": "INTELIGÊNCIA ARTIFICIAL",
    "Disc.Tec.": "DISCIPLINA TÉCNICA",
    # Adicionar conforme necessário
}

def mapear_disciplina(nome_grade: str) -> str:
    """Mapeia nome abreviado da grade para nome completo no banco."""
    return MAPPING_DISCIPLINAS.get(nome_grade, nome_grade)
```

### 2. Cálculo Automático do Número da Aula

```python
def calcular_n_aula_automatico(disciplina_id: int) -> int:
    """Calcula o número da aula baseado no histórico de registros."""
    if not db or not db.is_db_connected():
        return 1
    
    try:
        # Busca total de registros existentes
        hist_count = db.supabase.table("historico_aulas")\
            .select("*", count='exact')\
            .eq("disciplina_id", disciplina_id)\
            .execute()
        
        n_aula = (hist_count.count or 0) + 1
        
        # Verifica limite de carga horária
        subjects = db.get_subjects_for_class(...)
        num_subjects = len(subjects) if subjects else 10
        limit_lessons = 400 // num_subjects
        
        return min(limit_lessons, n_aula)
    except:
        return 1
```

### 3. Auto-preenchimento de Conteúdo

```python
def auto_preencher_conteudo(turma_nome: str, disciplina_nome: str, aula_num: int) -> dict:
    """Preenche automaticamente todos os campos de conteúdo."""
    
    # 1. Busca no catálogo de arquivos .md
    dados_md = extrair_dados_aula_md(turma_nome, disciplina_nome, aula_num)
    
    # 2. Busca no banco de dados
    lesson_db = None
    if db and db.is_db_connected():
        disciplina_nomeCompleto = mapear_disciplina(disciplina_nome)
        subjects = db.get_subjects_for_class(...)
        for s in subjects:
            if disciplina_nomeCompleto.upper() in s['name'].upper():
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
    
    # 4. Determina fonte
    if lesson_db:
        fonte = "banco de dados"
    elif dados_md.get('found'):
        fonte = "arquivo local"
    else:
        fonte = "padrão"
    
    return {
        'titulo': titulo,
        'objetivos': objetivos,
        'atividade': atividade,
        'recursos': recursos,
        'fonte': fonte,
        'lesson_db': lesson_db,
        'dados_md': dados_md
    }
```

### 4. Verificação de Plano Existente

```python
def verificar_plano_existente(turma_id: int, disciplina_id: int, aula_num: int) -> dict:
    """Verifica se já existe plano gerado para esta aula."""
    nome_arquivo = f"PLANO_TURMA_{turma_id}_DISC_{disciplina_id}_AULA_{aula_num:02d}.txt"
    caminho = os.path.join(OUTPUT_DIR_REPO, nome_arquivo)
    
    if os.path.exists(caminho):
        with open(caminho, 'r', encoding='utf-8') as f:
            conteudo = f.read()
        
        # Extrai dados do plano existente
        match_data = re.search(r'DATA:\s*(\d{4}-\d{2}-\d{2})', conteudo)
        match_titulo = re.search(r'\[CONTEUDO\]\n(.*?)(?=\n\n|\Z)', conteudo, re.DOTALL)
        
        return {
            'existe': True,
            'data': match_data.group(1) if match_data else "desconhecida",
            'titulo': match_titulo.group(1).strip() if match_titulo else "N/A",
            'caminho': caminho,
            'tamanho': os.path.getsize(caminho)
        }
    
    return {'existe': False}
```

### 5. Cálculo de Datas Sequenciais

```python
def calcular_datas_sequenciais(turma_nome: str, disciplina_nome: str, data_inicio: date, num_aulas: int) -> list:
    """Calcula datas sequenciais baseado na grade semanal."""
    grade = carregar_grade_semanal()
    
    # Identifica os dias da semana que a disciplina tem aula
    dias_disciplina = set()
    if turma_nome in grade:
        for dia, horarios in grade[turma_nome].items():
            if isinstance(horarios, dict):
                for horario, disc in horarios.items():
                    if disciplina_nome.upper() in str(disc).upper():
                        dias_disciplina.add(dia)
    
    if not dias_disciplina:
        # Fallback: assume segunda a sexta
        dias_disciplina = {"Segunda", "Terça", "Quarta", "Quinta", "Sexta"}
    
    # Calcula as datas
    datas = []
    data_atual = data_inicio
    dias_semana_map = {0: "Segunda", 1: "Terça", 2: "Quarta", 3: "Quinta", 4: "Sexta", 5: "Sábado", 6: "Domingo"}
    
    while len(datas) < num_aulas:
        dia_nome = dias_semana_map[data_atual.weekday()]
        if dia_nome in dias_disciplina:
            datas.append(data_atual)
        data_atual += timedelta(days=1)
    
    return datas
```

---

## Checklist de Implementação

### Fase 1 (1 semana)
- [ ] Adicionar `MAPPING_DISCIPLINAS` no topo do arquivo
- [ ] Implementar `mapear_disciplina()`
- [ ] Implementar `calcular_n_aula_automatico()`
- [ ] Implementar `auto_preencher_conteudo()`
- [ ] Implementar `verificar_plano_existente()`
- [ ] Modificar `render()` para usar auto-preenchimento
- [ ] Adicionar indicador de fonte dos dados
- [ ] Testar fluxo completo

### Fase 2 (1 semana)
- [ ] Implementar `calcular_datas_sequenciais()`
- [ ] Auto-sugerir disciplina pela grade
- [ ] Adicionar detecção de conflitos
- [ ] Melhorar interface com 4 passos claros

### Fase 3 (1 semana)
- [ ] Gerar semana inteira com datas corretas
- [ ] Preview em lote
- [ ] Exportação ZIP

### Fase 4 (2 semanas)
- [ ] Integração com `historico_aulas`
- [ ] Verificação de duplicatas
- [ ] Sincronização com portal

---

## Métricas de Sucesso

| Métrica | Antes | Depois (meta) |
|---------|-------|---------------|
| Tempo por plano | ~3 min | ~30 seg |
| Cliques necessários | ~15 | ~5 |
| Campos manuais | ~8 | ~2 |
| Erros de número de aula | Comum | Eliminado |
| Planos duplicados | Possível | Bloqueado |
| Uso pelo professor | "Apenas em necessidade" | "Uso regular" |
