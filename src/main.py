#  執行方式 streamlit run main.py
#
import os
import json
import streamlit as st
import pandas as pd
import sqlalchemy as sa
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
from streamlit_chat import message
from dotenv import load_dotenv
from langchain.embeddings import OpenAIEmbeddings
from langchain import LLMChain,PromptTemplate
from langchain.chat_models import AzureChatOpenAI
from langchain.document_loaders import WikipediaLoader
from langchain.llms import OpenAI
from langchain.schema import (
    SystemMessage,
    HumanMessage,
    AIMessage
)

# 設定呼叫 OpenAI API 所需連線資訊
chat_model = 'gpt-35-turbo'
embeddings_model = 'text-embedding-ada-002'

# 載入 Azure OpenAI Service API 相關資訊
load_dotenv()

# 建立 Azure OpenAI Chat 與 Embeddings 類別的實例
chat = AzureChatOpenAI(deployment_name=chat_model,model_name=chat_model,temperature=0, max_tokens=2000)
embeddings = OpenAIEmbeddings(deployment=embeddings_model, chunk_size = 16)

# 建立 Azure SQL Database 連線
connection_string = os.getenv("SQL_CONNECTION_STRING")
connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
sql_engine = create_engine(connection_url,connect_args={"timeout": 120})

def init():
    # 設定 streamlit 首頁
    st.set_page_config(
        page_title="Azure OpenAI Service ChatGPT 對話機器人",
        page_icon="🤖"
    )

def question_filter(input_str):
    try:
        prompt = PromptTemplate(input_variables=["prompt_str"],template="事實:{prompt_str}\n" \
                                             "事實中這句話的意圖是查詢嗎? 如果是並此問題可以在 Wikipedia 上查得到請回答一個字母 [Y]\n" \
                                             "事實中這句話的意圖是查詢嗎? 如果是並此問題無法在 Wikipedia 上查得到請回答一個字母 [N]\n" \
                                             "如果事實這句話的意圖不是查詢，請回答一個字母 [C]\n")
        # 將 AzureChatOpenAI 以 LLMChain 方式使用
        chain = LLMChain(llm=chat,prompt=prompt)
        response = chain.run(input_str)
    except Exception as e:
        print("發生錯誤: ", e)
        response = "發生了一點技術問題，我無法連線到 Azure OpenAI Service，請稍後再試"        
    return(response)

def get_query_english_keyword(input_str):
    try:
        prompt = PromptTemplate(input_variables=["prompt_str"],template="事實:{prompt_str}\n" \
                                                "將事實轉換為一句包含關鍵字的英文\n" \
                                                "English Fact:")
        # 將 AzureChatOpenAI 以 LLMChain 方式使用
        chain = LLMChain(llm=chat,prompt=prompt)
        response = chain.run(input_str)
    except Exception as e:
        print("發生錯誤: ", e)
        response = "發生了一點技術問題，我無法連線到 Azure OpenAI Service，請稍後再試"
    return(response)

def embeddings_query(input_str):
    try:
        # 查詢文字轉換為 OpenAI Embeddings 向量值，再轉為 JSON 格式字串
        response = embeddings.embed_query(input_str)
        json_str = json.dumps(response)        
        # 查出最新相關的 3 個條目
        sql = "select top 3 cosine_distance,title,url from dbo.SimilarContentArticles ('"+ json_str + "') as r order by cosine_distance desc"
        # 查詢結果置於 DataFrame    
        with sql_engine.connect() as conn:
            output_df = pd.read_sql_query(sa.text(sql), conn)              
    except Exception as e:
        print("發生錯誤: ", e)
        # 錯誤代處理
        output_df = pd.DataFrame()
    return (output_df)

def answer_summary (input_str,title):
    try:
        # 取得 Simple English Wikipedia 的網頁內容
        docs = WikipediaLoader(query=title, load_max_docs=1).load()
        html_body = docs[0].page_content[:2000]    
        # 將網頁內容轉換為摘要
        prompt = PromptTemplate(input_variables=["question_str","html_str"],template="事實:{question_str}\n" \
                                                "HTML:{html_str}\n" \
                                                "解析 HTML 的內容，依據這些內容以一百字摘要的方式，用繁體中文回答事實內提出的問題，" \
                                                "如果 HTML 解析出來的內容無法回答事實內的問題，則回覆 '很抱歉我不知道答案，這是最接近的條目'" \
                                                "回覆:")

        # 將 AzureChatOpenAI 以 LLMChain 方式使用
        chain = LLMChain(llm=chat,prompt=prompt)
        response = chain.run(question_str=input_str,html_str=html_body)
    except Exception as e:
        print("發生錯誤: ", e)
        # 發生錯誤時的回覆
        response = "資料庫連線或是 Wikipedia 內容載入發生了一點技術問題，我無法正常查詢與回覆內容。"
    return (response)

def main():
    init()

    # 起始 messages session
    if "messages" not in st.session_state:
        st.session_state.messages = [
            SystemMessage(content='你是一個針對 Wikipeida 內容查詢的繁體中文的對話機器人，以活潑風格回問題')
        ]
        st.session_state.messages.append(AIMessage(content="您好。我是一個可以運用 OpenAI Embeddings 比對查詢 Simple English Wikipeida 的對話機器人。"))

    st.header("Azure OpenAI Service 打造之 🤖")

    # 處理側邊用戶輸入
    with st.sidebar:
        user_input = st.text_input("輸入訊息: ", key="user_input")

        # 處理用戶輸入
        if user_input: 
            st.session_state.messages.append(HumanMessage(content=user_input))
            with st.spinner("思考中..."):
                # 判斷用戶輸入內容類型
                question_type = question_filter(user_input)
                if question_type == 'Y': 
                    # 將用戶輸入文字轉換為英文，以增加查詢準確度
                    english_keyword = get_query_english_keyword(user_input) 
                    # 將英文轉換為 OpenAI Embeddings 向量值，再轉為 JSON 格式字串對 SQL Server 進行餘懸進行餘弦相似度計算比對                  
                    respons_str = '這是用 OpenAI 所提供的 Simple English Wikipeida Embeddings 資料，比對出來最相關的三個條目，\n'
                    respone_df = embeddings_query(english_keyword)
                    # 顯示向量近似查詢結果於左側窗格
                    st.markdown("比對內容: "+ english_keyword)
                    st.dataframe(respone_df)
                    
                    # 取得第一個條目的標題，做內容為回覆摘要
                    if (len(respone_df.index)>0):
                        print (len(respone_df.index))
                        respons_str = respons_str + answer_summary (english_keyword,respone_df.iloc[0]['title']) + "\n\n 資料來源: \n"
                        # 將最接近的三個條目的網址加入參考資料
                        for index, row in respone_df.iterrows():
                            respons_str = respons_str + str(index+1)+". [*" + row['title'] + "*](" +  row['url'] + ") \n"                        
                    else:
                       respons_str = "LangChain 的 Wikipedia Loader 載入內容時發生了一點技術問題，我無法彙整出摘要。"     
                    
                    st.session_state.messages.append(AIMessage(content=respons_str))
                else:
                    if question_type == 'C':
                        # 非查詢類問題，讓 ChatGPT 模型自由回答
                        response = chat(st.session_state.messages)                        
                        # 將回覆資料加入對話歷史紀錄 
                        st.session_state.messages.append(AIMessage(content=response.content))
                    else:
                        # 處理無法回覆之查詢問題 
                        st.session_state.messages.append(AIMessage(content="很抱歉，我不知道 ..."))
                
    # 顯示對話歷史紀錄
    messages = st.session_state.get('messages', [])
    for i, msg in enumerate(messages[1:]):
        if i % 2 == 0:  
            # 用戶輸入          
            with st.chat_message("user"):
                st.markdown(msg.content)
            
        else:            
            # 機器人回覆
            with st.chat_message("assistant"):
                st.markdown(msg.content)
         

if __name__ == '__main__':
    main()