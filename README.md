Este repositório contém a aplicação e o dashboard desenvolvidos para o **Projeto Integrador e Extensionista** do curso de **Ciência de Dados e Inteligência Artificial** da **PUC-Campinas**.

## 🎯 Sobre o Projeto
A aplicação tem como objetivo realizar um diagnóstico territorial analítico da rede SUS na cidade de Campinas - SP, identificando as pressões estruturais sobre a atenção básica e a rede hospitalar. O projeto atende diretamente ao **Objetivo de Desenvolvimento Sustentável (ODS) 3 - Saúde e Bem-Estar**, fornecendo ferramentas visuais baseadas em dados para subsidiar estratégias de saúde pública e cobertura universal.

## 🗄️ Fontes de Dados Públicos
Cumprindo o requisito de integração de múltiplas fontes, a aplicação consolida dados de:
1. **CNES/DataSUS (API DEMAS):** Informações detalhadas sobre os estabelecimentos de saúde, coordenadas geoespaciais, tipo de unidade (UBS, UPA, Hospital) e vínculo com o SUS.
2. **IBGE (Censo 2022 - Tabela SIDRA 4709):** Dados populacionais e demográficos, utilizados para calcular indicadores de pressão como o *Risk Score* e a relação Habitantes/UBS.

## 🛠️ Tecnologias e Arquitetura

* **Linguagem:** Python
* **Banco de Dados Não Relacional:** MongoDB Atlas
* **Visualização de Dados e Dashboard:** Plotly, Leaflet, NetworkX
* **Bibliotecas auxiliares:** Pandas, Requests, Certifi

### Estrutura do Banco de Dados (MongoDB)
Todos os dados brutos foram pré-tratados em Python e inseridos no MongoDB de forma estruturada. A arquitetura conta com **3 coleções principais**:
* `regioes`: Agrega os indicadores consolidados, centroides geoespaciais e métricas de cobertura por distrito.
* `estabelecimentos`: Cadastro detalhado das unidades de saúde, incluindo índices geoespaciais (`2dsphere`).
* `relacoes`: Mapeamento hierárquico e de referência entre a atenção básica e a rede especializada/hospitalar.

Foram criados e utilizados **índices de agregação** complexos para garantir consultas rápidas aos indicadores de risco e plotagem dinâmica do mapa.

## 📊 Dashboard Analítico
O painel foi construído de forma responsiva em HTML/JS, consumindo os dados diretamente e dinamicamente do banco. Ele atende ao requisito visual com **mais de 6 gráficos distintos** e **1 grafo relacional**:

1. **Diagnóstico Executivo e KPIs:**
   ![Diagnóstico e KPIs](Captura%20de%20tela%202026-05-28%20170846.jpg)

2. **Risk Score por Distrito (Gráfico de Barras Duplo):**
   ![Risk Score](Captura%20de%20tela%202026-05-28%20170858.png)

3. **Ranking de Cobertura (Tabela Analítica):**
   ![Ranking de Cobertura](Captura%20de%20tela%202026-05-28%20170909.png)

4. **Composição da Rede (Barras Empilhadas e Donut Chart):**
   ![Composição da Rede](Captura%20de%20tela%202026-05-28%20170920.png)

5. **Perfil Multidimensional (Radar Chart):**
   ![Perfil Multidimensional](Captura%20de%20tela%202026-05-28%20170930.png)

6. **Hierarquia da Rede SUS (Treemap interativo):**
   ![Hierarquia da Rede](Captura%20de%20tela%202026-05-28%20170942.png)

7. **Grafo: Rede de Referência Hospitalar (Diagrama Sankey):**
   *Atende ao requisito de grafo de relacionamento da aplicação.*
   ![Grafo Sankey](Captura%20de%20tela%202026-05-28%20170955.png)

8. **Geografia da Saúde (Mapa Geoespacial com Leaflet):**
   ![Mapa Geoespacial](Captura%20de%20tela%202026-05-28%20171010.jpg)

9. **Conclusões Estratégicas e Metodologia:**
   ![Conclusões](Captura%20de%20tela%202026-05-28%20171024.jpg)

## 🚀 Como Executar o Projeto

1. Clone este repositório.
2. Instale as dependências necessárias utilizando o arquivo `requirements.txt`:
   ```bash
   pip install plotly networkx pandas requests pymongo certifi