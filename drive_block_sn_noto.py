#!/usr/bin/env python
# coding: utf-8

# In[1]:


#import modules
import pandas as pd
import gspread
import json
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from oauth2client.service_account import ServiceAccountCredentials
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from datetime import datetime, date, timedelta
from time import sleep
from sqlalchemy import create_engine, text
import numpy as np
from slack import WebClient


# In[2]:


#credentials
access = open('C://access.JSON')
access = json.load(access)

#read the DWH credentials
db = open('C://useralchemy.txt').read()[1:-1]

#connect to DWH
db = create_engine(db,isolation_level="AUTOCOMMIT")


# In[3]:


query = open(r'G:\Shared drives\Verificação - Monitoring\Automação\Handover Davi\block_serial_noto\block_sn.sql').read()

res = db.execute(query)

df = pd.DataFrame(res,columns = ['merchant_code','merchant_id','serial_number'])

#Checa se algum dos mids possuem troca de leitor recente, pois o s/n pertencerá a outro mid no futuro

query = open(r'G:\Shared drives\Verificação - Monitoring\Automação\Handover Davi\block_serial_noto\order_consult.sql').read()

list_consult = tuple(set(df.merchant_code))

order_consult = query.replace('list_consult', str(list_consult))

res = db.execute(order_consult)

df_order = pd.DataFrame(res,columns = ['merchant_code'])

df_order = list(df_order.merchant_code)

#Remove os mids que tiveram troca de S/N recente
df['duplicate'] = df.merchant_code.isin(df_order)
df = df[df.duplicate == False]
df.drop(columns = ['duplicate'], inplace = True)


# In[5]:


#conecta com a google sheets para remover os duplicados
#Credentials Google
google_credentials = 'C://google_credentials.json'
adress_sheet = '1RFYiouH3X-KLf7yXctE_Ys-ddIiM_JqMmfuYqAK81U8'
name_work_sheet = 'base'
scope = ['https://www.googleapis.com/auth/drive']

#pass credential
credentials = ServiceAccountCredentials.from_json_keyfile_name(google_credentials, scope)

#get authorize to acess
gc = gspread.authorize(credentials)
sh = gc.open_by_key(adress_sheet)

#pass name of sheet and get all values of sheet
worksheet = sh.worksheet(name_work_sheet) #get_worksheet(0)
model = worksheet.get_all_values()


#define name of columns and input sheet in the Data Frame
headers = model.pop(0)
df2 = pd.DataFrame(model,columns=headers)

#pega os valores da google sheets e armazena numa lista 
list_serial = pd.DataFrame(worksheet.get_all_values()).iloc[:,2].to_list()
#cria uma coluna e cruza os duplicados
df['duplicate'] = df.serial_number.isin(list_serial)
#filtra e armazena os não duplicados
df = df[df.duplicate == False]
#elimina a coluna duplicate
df.drop(columns = ['duplicate'], inplace = True)

print(len(df))


# In[6]:


if len(df)> 0:
    #instala o edge driver
    driver = driver = webdriver.Edge(EdgeChromiumDriverManager().install())

    driver.maximize_window()

    driver.get('https://oculus.notolytix.com/#!/login')

    sleep(7)
    #login
    driver.find_element_by_xpath('/html/body/div/main/section/div/div/div/div[2]/div/input').send_keys(access.get('email'))

    sleep(3)
    #password
    driver.find_element_by_xpath('/html/body/div/main/section/div/div/div/div[3]/div/input').send_keys(access.get('noto_key'))

    sleep(3)

    # Verificar se o login foi realizado com sucesso
    #pyautogui.alert('Clique em OK após realizar o login')

    driver.find_element_by_css_selector('#_2rzVLv81 > section > div > div > div > button > span').click()
    sleep(10)

    #brazil
    driver.find_element_by_xpath('/html/body/div/main/section/section[2]/div[1]/div/div/div/div[1]').click()

    sleep(5)

    driver.find_element_by_css_selector('#_3bsyA46u > div._3HB0wzyt > div:nth-child(2) > div').click()

    sleep(2)

    driver.find_element_by_css_selector('[data-testid="7"]').click()

    def move_to_transactions():
        el = driver.find_element_by_xpath("/html/body/div/main/section/section[2]/div/div/div/div/div[2]/div/div[8]")
        action = webdriver.common.action_chains.ActionChains(driver)
        action.move_to_element_with_offset(el, 5, 5)
        action.click()
        action.perform()
        sleep(5)

    try:
        driver.find_element_by_xpath('/html/body/div/main/section/section[2]/div/div/div/div/div[2]/div/div[8]').click()
    except:
        move_to_transactions()
        driver.find_element_by_xpath('/html/body/div/main/section/section[2]/div/div/div/div/div[2]/div/div[8]').click()
    sleep(3)

    driver.get('https://oculus.notolytix.com/lists/channel/Block_Terminals_of_Blocked_Merchants')

    sleep(5)

    def block_reader(mid, serial_number):
        try:
            driver.find_element_by_css_selector('#aCu1Wkjl > section > section > div._2FMESxkW > button:nth-child(1)').click()
            sleep(2)
            driver.find_element_by_css_selector('#aCu1Wkjl > section > div._1wQm3Utp > div > div > div:nth-child(1) > div > div > div > input').send_keys(serial_number)
            sleep(2)
            driver.find_element_by_css_selector('#aCu1Wkjl > section > div._1wQm3Utp > div > footer > button > span').click()
            sleep(3)

            acao = f'{mid} - Leitor bloqueado - {serial_number}'
            return acao
        except:
            driver.get('https://oculus.notolytix.com/lists/channel/Block_Terminals_of_Blocked_Merchants')
            sleep(3)
            acao = f'{mid} - Não foi possível bloquear este leitor '
            return acao
    #looping para bloquear os leitores e adicionar na lista
    list_acao = []
    for mid, serial_number in zip (df.merchant_code, df.serial_number):
        list_acao.append(block_reader(mid, serial_number))
    df['acao'] = list_acao
    driver.quit()
    #Faz o update dos mids e s/n bloqueados na gsheets
    data = date.today()
    data_hoje = data.strftime('%d/%m/%Y')
    df['data'] = data_hoje

    df = df[['merchant_code', 'merchant_id', 'serial_number', 'acao','data']].copy()

    sh = gc.open_by_key(adress_sheet)

    worksheet.append_rows(df.values.tolist())
else:
    pass


# In[7]:


#client slack (data of app) and chanell
slack_client_code = 'xoxb-2556537568-1370706200529-g3FO2KdGk6JjYoI8AQ68GGh8'
chanell_of_slack = 'C01Q7GN57EE'

#Mensagem Slack
try:
    client = WebClient(slack_client_code)
    response = client.chat_postMessage(
                    channel=chanell_of_slack,
                    text=f"BOT - BLOCK S/N NOTO - {len(df.serial_number)} BLOCKED")
except:
    pass


# In[8]:


#login google pra upar logs
google_credentials = 'C:\\google_credentials.json'
relat_adress_sheet = '117N6qxxVgX03AiqHx4zC7QsM8QkdrG6XMhbWeX23r3Q'
name_work_sheet = 'Rotina de execução'
name_log_sheet = 'log_exec'
scope = ['https://www.googleapis.com/auth/drive']
#pass credential
credentials = ServiceAccountCredentials.from_json_keyfile_name(google_credentials, scope)
#get authorize to acess
gc = gspread.authorize(credentials)
#pass key of worksheet
sh = gc.open_by_key(relat_adress_sheet)
#pass name of sheet and get all values of sheet
worksheet = sh.worksheet(name_work_sheet)
log_sheet = sh.worksheet(name_log_sheet)
####################################################################
###############upando info do relaorio##############################
#atualizando a celula do bot (cada um tem uma)
executed_time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
cell = worksheet.acell('B15')  # Specify the cell you want to update
cell.value = f"{executed_time}"  # Update the value
# Save the changes to the worksheet
worksheet.update_cell(cell.row, cell.col, cell.value)
print('Log upado na aba de Execução diária!')
#gerando log
relatorio_diario = worksheet.get_all_values()
headers = relatorio_diario.pop(0)
dfrelat = pd.DataFrame(relatorio_diario,columns=headers)
dfrelat.loc[0, 'Executado pela última vez em:'] = executed_time
updated_data = dfrelat.loc[0, ['Bot', 'Executado pela última vez em:']].tolist()
updated_data[1] = datetime.strptime(updated_data[1], "%d-%m-%Y %H:%M:%S").strftime("%d-%m-%Y")

