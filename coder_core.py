# coder_core.py

from langchain_community.llms import Ollama
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
# coder_core.py

import logging
import os
import time
import re
# ... outros imports


# Configurar logging
logging.basicConfig(level=logging.INFO)

class ModeloLLM:
    def __init__(self, nome_modelo="llama3.2"):
        self.modelo = Ollama(model=nome_modelo)
    
    def gerar(self, prompt, max_tokens, temperatura):
        """
        Gera uma resposta do modelo LLM com base no prompt fornecido.
        
        Args:
            prompt (str): O texto de entrada para o modelo.
            max_tokens (int): O número máximo de tokens na resposta.
            temperatura (float): A temperatura para amostragem.
        
        Returns:
            str: A resposta gerada pelo modelo após processamento.
        """
        return make_api_call(self.modelo, prompt, max_tokens, temperatura)


def make_api_call(model, prompt, max_tokens, temperature):
    for attempt in range(3):
        try:
            logging.info(f"Tentativa {attempt + 1} de 3 para gerar resposta.")
            response = model.generate([prompt], model_kwargs={"max_tokens": max_tokens, "temperature": temperature})
            generated_text = response.generations[0][0].text.strip()

            logging.info("Resposta bruta gerada pelo modelo:")
            logging.info(generated_text)

            # Processar a resposta para garantir apenas um bloco de código com comentários multilinha
            processed_text = process_llm_response(generated_text, model, max_tokens, temperature)

            logging.info("Resposta processada pelo modelo:")
            logging.info(processed_text)

            return processed_text
        except Exception as e:
            logging.error(f"Exception: {str(e)}")
            if attempt == 2:
                return f"Falha ao gerar resposta após 3 tentativas. Erro: {str(e)}"
            time.sleep(0.3)



class VectorStoreManager:
    def __init__(self, vectorstore_path="vectorstore"):
        self.embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
        self.vectorstore_path = vectorstore_path
        self.vectorstore = self.initialize_vectorstore()

    def initialize_vectorstore(self):
        if not os.path.exists(self.vectorstore_path):
            os.makedirs(self.vectorstore_path)
        return Chroma(persist_directory=self.vectorstore_path, embedding_function=self.embeddings)

    def search_documents(self, query, k=3):
        return self.vectorstore.similarity_search(query, k=k)

class CoderCore:
    def __init__(self):
        self.model = ModeloLLM()
        self.vectorstore_manager = VectorStoreManager()

    def generate_subqueries(self, prompt):
        """
        Descompor o prompt principal em subconsultas resolvíveis usando cadeia de pensamento.
        """
        subquery_prompt = f"Descomponha a seguinte consulta em uma série de subconsultas menores e gerenciáveis: \n{prompt}"
        response = self.model.gerar(subquery_prompt, max_tokens=200, temperatura=0.5)
        # Utilizar expressões regulares para uma divisão mais robusta
        subqueries = re.split(r'\n|- ', response)
        return [subquery.strip() for subquery in subqueries if subquery.strip()]

    def generate_code_solution(self, user_query, chain_of_thought, final_answer):
        """
        Gerar uma solução de código para abordar a consulta com base na cadeia de pensamento e na resposta final.
        """
        if not chain_of_thought or not final_answer:
            return ""
        code_prompt = f"""Com base na cadeia de pensamento e na resposta final fornecidas, gere um código que resolva o problema descrito na consulta do usuário:

Consulta do Usuário: {user_query}

Cadeia de Pensamento: {chain_of_thought}

Resposta Final: {final_answer}

Solução de Código:"""
        generated_code = self.model.gerar(code_prompt, max_tokens=500, temperatura=0.7)
        return generated_code.strip()

    def process_query(self, user_query, chat_history, existing_code=None):
        """
        Processar a consulta do usuário, gerar subconsultas e implementar estratégias de cadeia de pensamento.
        """
        # Determinar a complexidade
        existing_code = existing_code if existing_code is not None else ""
        is_complex = self.decide_complexidade_pergunta(user_query, chat_history, existing_code)
        response, steps = self.responde_chain_of_thought(user_query, chat_history, existing_code, is_complex)
        return response, steps

    def decide_complexidade_pergunta(self, pergunta, chat_history, existing_code=""):
        """
        Determina se a pergunta requer uma resposta simples ou complexa com base no contexto das últimas mensagens e no código existente.
        """
        last_messages = "\n".join(chat_history[-5:])
        similar_docs = self.vectorstore_manager.search_documents(pergunta, k=3)
        similar_texts = "\n".join([doc.page_content for doc in similar_docs])

        prompt = f"""
Considere o contexto das últimas 5 mensagens abaixo:

{last_messages}

Além disso, considere os seguintes documentos similares:

{similar_texts}

E considere o código atual:

{existing_code}

Com base nesse contexto e na pergunta a seguir:

Pergunta: {pergunta}

Determine se a pergunta requer uma resposta simples ou complexa.
Responda apenas com "Simples" ou "Complexa".
"""

        resposta = self.model.gerar(prompt, max_tokens=10, temperatura=0.3)
        return resposta.strip().lower() == "complexa"

    def responde_chain_of_thought(self, pergunta, chat_history, existing_code="", is_complex=False):
        """
        Responde a uma pergunta utilizando uma cadeia de pensamento simples ou complexa dependendo da complexidade.
        """
        lista_passos = [
            "Compreensão da pergunta",
            "Identificação dos dados relevantes",
            "Formulação de hipóteses",
            "Análise lógica",
            "Verificação da consistência",
            "Síntese da resposta",
            "Revisão e refinamento"
        ]

        prompt_contexto_codigo = f"O código atual é:\n{existing_code}\n\n"

        if is_complex:
            prompt_cadeia = f"""
Pergunta: {pergunta}
{prompt_contexto_codigo}
Gere uma cadeia de pensamento complexa para responder à pergunta acima, usando os seguintes passos:
{', '.join(lista_passos)}
Forneça uma resposta detalhada para cada passo.
"""
        else:
            prompt_cadeia = f"""
Pergunta: {pergunta}
{prompt_contexto_codigo}
Gere uma cadeia de pensamento simples para responder à pergunta acima, usando os seguintes passos:
{', '.join(lista_passos)}
Forneça uma resposta concisa para cada passo.
"""
        
        cadeia = self.model.gerar(prompt_cadeia, max_tokens=500, temperatura=0.7)
        
        prompt_resposta = f"""
Com base na seguinte cadeia de pensamento:
{cadeia}
Forneça uma resposta direta e concisa para a pergunta original: {pergunta}
"""
        resposta = self.model.gerar(prompt_resposta, max_tokens=200, temperatura=0.5)
        
        return resposta.strip(), [cadeia]

    def create_code_solution_if_empty(self, user_query, chain_of_thought, final_answer, existing_code):
        """
        Cria uma nova solução de código apenas se o editor de código estiver vazio ou sugere modificações no código existente.
        """
        if not existing_code.strip():
            return self.generate_code_solution(user_query, chain_of_thought, final_answer)
        else:
            return self.suggest_code_modification(user_query, chain_of_thought, final_answer, existing_code)

    def suggest_code_modification(self, user_query, chain_of_thought, final_answer, existing_code):
        """
        Sugere modificações no código existente com base na nova consulta e na cadeia de pensamento.
        """
        modification_prompt = f"""
O código atual é:
{existing_code}

Com base na consulta do usuário: {user_query}
E na cadeia de pensamento: {chain_of_thought}
Sugira modificações ou melhorias no código existente para atender à consulta.
"""
        suggested_code = self.model.gerar(modification_prompt, max_tokens=300, temperatura=0.7)
        return suggested_code.strip()


def process_llm_response(text, model, max_tokens, temperature, recursion_depth=0, max_recursion=5):
    """
    Processa a resposta do LLM para garantir que haja apenas um bloco de código.
    Adiciona comentários multilinha para descrição e observação.
    """
    # Encontrar todos os blocos de código Python
    code_blocks = re.findall(r'```python(.*?)```', text, re.DOTALL)

    if len(code_blocks) > 1 and recursion_depth < max_recursion:
        logging.info(f"{len(code_blocks)} blocos de código encontrados. Solicitando síntese ao LLM.")
        synthesis_prompt = f"""
A resposta fornecida contém múltiplos blocos de código. Por favor, sintetize todos os blocos de código abaixo em um único bloco de código funcional.

Resposta Original:
{text}

Resposta Sintetizada:
```
python
# Código sintetizado
```
"""
        synthesized_response = make_api_call(model, synthesis_prompt, max_tokens, temperature)
        return process_llm_response(synthesized_response, model, max_tokens, temperature, recursion_depth + 1, max_recursion)
    elif len(code_blocks) == 1:
        logging.info("Apenas um bloco de código encontrado. Adicionando comentários multilinha.")
        # Extrair o bloco de código
        code = code_blocks[0].strip()

        # Remover qualquer descrição e observação anteriores
        code = re.sub(r'\"\"\"(?:Descripção|Observação):.*?\"\"\"', '', code, flags=re.DOTALL)

        # Adicionar comentários multilinha
        final_code = f"""\"\"\"
Descrição:
{extract_description(text)}

Observação:
{extract_observation(text)}
\"\"\"
{code}
\"\"\"
Observação Adicional:
Nenhuma observação adicional.
\"\"\""""

        return final_code
    else:
        # Nenhum bloco de código encontrado
        logging.info("Nenhum bloco de código encontrado na resposta.")
        return text

def extract_description(text):
    """
    Extrai a descrição do texto fornecido.
    """
    # Implementar lógica para extrair a descrição conforme necessário
    # Por exemplo, pode-se usar regex ou outra abordagem
    return "Descrição padrão."

def extract_observation(text):
    """
    Extrai a observação do texto fornecido.
    """
    # Implementar lógica para extrair a observação conforme necessário
    return "Observação padrão."