#!/usr/bin/env python

from urllib.request import urlopen
import requests
from bs4 import BeautifulSoup
import numpy as np
import pandas as pd
import datetime
import algosdk
import math
import time
import io
import os
from pdfminer.converter import HTMLConverter,TextConverter
from pdfminer.pdfinterp import PDFPageInterpreter,PDFResourceManager
from pdfminer.pdfpage import PDFPage
from pdfminer.layout import LAParams


class TestingData_Scraper() :

    def __init__(self,Impute=False) :

        self.url_positive_cases = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_US.csv"
        self.url_deaths = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_deaths_US.csv"

        self.Gen_Date_Columns()

    def Gen_Date_Columns(self) :

        column_range = []
        date_add =  datetime.datetime.strptime('1/22/20','%m/%d/%y')
        while date_add < datetime.datetime.today() :
            column_range.append(date_add)
            date_add += datetime.timedelta(days=1)
        column_range = [datetime.datetime.strftime(date,'%m/%d/%y') for date in column_range]
        column_range = ['/'.join([a.lstrip('0') for a in date.split('/')]) for date in column_range]
        
        self.date_columns = column_range

    def Impute_Values(self,df) :

        for i,v in df.iterrows() :
            cases_ck = v[self.date_columns].to_list()
            for j,col in enumerate(cases_ck) :
                if j == 0 :
                    continue
                to_add = col if col >= cases_ck[j-1] else cases_ck[j-1]
                cases_ck[j] = to_add
            df.loc[i,self.date_columns] = cases_ck

    def Get_Final_DF(self,Impute = False) :

        cases = pd.read_csv(self.url_positive_cases)
        deaths = pd.read_csv(self.url_deaths)

        self.date_columns = [col for col in self.date_columns if col in cases.columns]

        if Impute :
            print('Imputing values where errors in cumulative stats.')
            self.Impute_Values(cases)
            self.Impute_Values(deaths)

        id_vars = [col for col in cases.columns if col not in self.date_columns]
        cases = cases.melt(id_vars=id_vars,var_name='Date',value_name='Positive')

        id_vars = [col for col in deaths.columns if col not in self.date_columns]
        deaths = deaths.melt(id_vars=id_vars,var_name='Date',value_name='Deaths')

        Testing_DF = cases
        Testing_DF['Deaths'] = deaths['Deaths']
        return Testing_DF


class Algorand_Scrape():
    
    def __init__(self, api_key):
        self.purestake_api_key = api_key
        self.connectMainnet()
        self.client_check()
        
        # For retrieving the real covid data from mainnet
        self.address = "COVIDR5MYE757XMDCFOCS5BXFF4SKD5RTOF4RTA67F47YTJSBR5U7TKBNU"
        self.fromRound = 5646000
        self.maxTxnPerCall = 500 # max transactions in a batch
        batchSize = 512 #Read the transactions from the blockchain in 512-block installations
        self.params = self.algod_client.suggested_params()
        self.lastRound = self.params['lastRound']
        #self.lastRound = self.fromRound + 20*self.batchSize # for testing
        
        print("\n total rounds:",self.lastRound - self.fromRound)
        
        self.txns = []
        
        rnd = self.fromRound
        while rnd < self.lastRound:
            toRnd = rnd + batchSize
            if toRnd > self.lastRound:
                toRnd = self.lastRound
            to_add = self.getTransactionBatch(rnd,toRnd) # Fetch transactions for these rounds
            self.txns.extend(to_add)  
            rnd += batchSize
            time.sleep(.1) #added because was overloading 
        print("found {} transactions".format(len(self.txns)))

        self.header_descriptions = {'a':'','_t':'','_v':'','gc':'string, country code (see Location Data section below)',
            'gr':'string, region code  (see Location Data section below)',
            'gzp':'string, 3-digit zip code (US only)',
            'ga':'integer, age group, if present must be in 1,11,21,31,41,51,56,61,66,71,76,81,85',
            'gs':'string , gender, if present must be "m","f"',
            'sz':'integer, is symptomatic, no-answer=0/no=-1/yes=1',
            's1':'boolean, fever',
            's2':'boolean, cough',
            's3':'boolean, difficulty breathing',
            's4':'boolean, fatigue',
            's5':'boolean, sore throat',
            'sds':'date, when symptoms started, yyyy-mm-dd',
            'sde':'date, when symptoms ended, yyyy-mm-dd',
            'sdn':'boolean, still symptomatic',
            'tz':'integer, tested, no-answer=0/no=-1/yes=1',
            'tt':'integer, tried to get tested, no=-1, yes=1, yes but was denied=2',
            'td':'date, test date, yyyy-mm-dd',
            'tr':'integer, test results, -1=negative,1=positive,2=waiting for result',
            'tl':' integer, test location, 1=Dr office/2=Hospital/3=Urgent care/4=Ad-hoc center/5=Other medical care',
            'mz':' integer, received care, no-answer=0/no=-1/yes=1',
            'm1':' boolean, doctor office',
            'm2':' boolean, walk-in clinic',
            'm3':' boolean, virtual care',
            'm4':' boolean, hospital/ER',
            'm5':' boolean, other',
            'mh':' integer, hospitalized, no-answer=0/no=-1/yes=1',
            'mhs':' date, when admitted, yyyy-mm-dd',
            'mhe':' date, when discharged, yyyy-mm-dd',
            'mhn':' boolean, still in hospital',
            'qz':'integer, was quarantined, no-answer=0/no=-1/yes=1',
            'q1':'boolean, due to symptoms',
            'q2':'boolean, voluntarily',
            'q3':'boolean, personally required',
            'q4':'boolean, general quarantine',
            'qds':'date, when quarantine started, yyyy-mm-dd',
            'qde':'date, when quarantine ended, yyyy-mm-dd',
            'qdn':'boolean, still quarantined',
            'ql':'integer, left quarantine temporarily no-answer=0/no=-1/yes=1',
            'consent':'boolean , user consent, mandatory, must be "true"'}
                             
    def connectMainnet(self):
        algod_address_mainnet = "https://mainnet-algorand.api.purestake.io/ps1"
        port = ""
        token = {
            'X-API-key' : self.purestake_api_key,
        }
        # Initialize the algod client
        self.algod_client = algosdk.algod.AlgodClient(port, algod_address_mainnet, token) 
    
    def client_check(self):
        try:
            status = self.algod_client.status()
        except Exception as e:
            print("Failed to get algod status: {}".format(e))

        if status:
            print("algod last round: {}".format(status.get("lastRound")))
            print("algod time since last round: {}".format(status.get("timeSinceLastRound")))
            print("algod catchup: {}".format(status.get("catchupTime")))
            print("algod latest version: {}".format(status.get("lastConsensusVersion")))

        # Retrieve latest block information                                                                                                                                               
        last_round = self.algod_client.status().get("lastRound")
        print("####################")
        block = self.algod_client.block_info(last_round)
        print(block)
                             
    def getTransactionBatch(self,fromRnd,toRnd):
        if (fromRnd > toRnd):# sanity check
            return []
        txs = self.algod_client.transactions_by_address(self.address,fromRnd,toRnd,self.maxTxnPerCall) 
        # make an API call to get the transactions - 500 at a time

        #  A recursive function for getting a batch of transactions, to overcome
        # the limitation of maxTxnPerCall transaction per call to the API
        if (fromRnd == toRnd) | (len(txs['transactions']) < self.maxTxnPerCall) :
            return txs['transactions']
        else :
            midRnd = math.floor((fromRnd+toRnd) / 2)
            txns1 = getTransactionBatch(fromRnd, midRnd)
            txns2 = getTransactionBatch(midRnd+1, toRnd)
            return txns1.concat(txns2)

    def get_txns(self) :
        return self.txns

    def Convert_to_DF(self) :

        alg_txs = self.get_txns()

        Survey_DF = pd.DataFrame()

        ###### DECODING DATA
        for i in range(len(alg_txs)):
            #if (i%1000 == 0): print("{} transactions decoded".format(i))
            tx_dict = alg_txs[i]
            tx_code = tx_dict['tx']
            encoded_note = tx_dict['noteb64']
            decoded_note = algosdk.encoding.msgpack.unpackb(algosdk.encoding.base64.b64decode(encoded_note))
            decoded_note = decoded_note['d']
            decoded_note_data = {
                key.decode() if isinstance(key, bytes) else key:
                val.decode() if isinstance(val, bytes) else val
                for key, val in decoded_note.items()
            }
            decoded_note_data.update({'a':tx_code})
            cleaned_note_data = {key:None for key in self.header_descriptions.keys()}
            cleaned_note_data.update(decoded_note_data)
            #print(cleaned_note_data)
            Survey_DF = Survey_DF.append(cleaned_note_data, ignore_index=True)
        
        return Survey_DF



class Wiki_Scrape() :

    def __init__(self) :

        self.url = "https://en.wikipedia.org/wiki/County_(United_States)"
        html = urlopen(self.url)
        self.soup = BeautifulSoup(html, 'html.parser')

    def Scrape_Counties(self) :

        table_look = self.soup.find("table",{"class":"wikitable sortable"}).find('tbody').findAll('tr')[2:]

        output_list = []
        counter = 0
        while True :
            if table_look[counter].get('class',[]) :
                break
            state = table_look[counter]
            counter += 1
            
            state_url = state.findAll('a')[1]['href']
            state_url = '/'.join(self.url.split('/')[:-2]) + state_url
            if len(state_url.split('_in_')) == 1 :
                state = state_url.split('/')[-1].replace('_',' ')
            else :
                state = state_url.split('_in_')[-1]
            print(state,end=',')
            state_html = urlopen(state_url)
            state_soup = BeautifulSoup(state_html, 'html.parser')
            if state == 'District of Columbia' :
                area = state_soup.find('table',{'class':"infobox geography vcard"}).findAll('tr')[21].find('td').getText().replace(u'\xa0', u' ').split(' ')[0]
                output_list.append([state,state,area])
                continue
            column_header_use = [i for i,a in 
                         enumerate(state_soup.find("table",{"class":"wikitable sortable"}).find('tbody').findAll('tr')[0].findAll('th')) if 
                         'Area' in a.getText()][0]
            to_iter = state_soup.find("table",{"class":"wikitable sortable"}).find('tbody').findAll('tr')[1:]
            for county in to_iter :
                county_name = county.find('th').find('a').getText()
                sq_miles = county.findAll('td')[column_header_use-1].findAll('span')[0].getText()
                output_list.append([state,county_name,sq_miles])

        return np.array(output_list)


class Alphabet_Scrape() :

    def __init__(self) :

        self.url = "https://www.google.com/covid19/mobility/"
        html_all = urlopen(self.url)
        soup_all = BeautifulSoup(html_all, 'html.parser')
        self.tmp_file = './report.pdf.tmp'

        self.US_html = self.get_country(soup_all)

    def convert_pdf_to_html(self,fname,pages=None,skip_first=True) :

        if not pages: 
            pagenums = set()
        else:         
            pagenums = set(pages)      
        manager = PDFResourceManager() 
        codec = 'utf-8'
        caching = True

        output = io.BytesIO()
        converter = HTMLConverter(manager, output, codec=codec, laparams=LAParams())

        interpreter = PDFPageInterpreter(manager, converter)   
        infile = open(fname, 'rb')
        
        print('Processing Page # :',end=' ')
        for i,page in enumerate(PDFPage.get_pages(infile, pagenums,caching=caching, check_extractable=True)):
            if skip_first :
                if i in [0,1] :
                    continue
            print(i,end=',')
            interpreter.process_page(page)

        convertedPDF = output.getvalue()  

        infile.close(); converter.close(); output.close()
        return convertedPDF

    def get_country(self,soup) :

        country_descriptions = soup.findAll(class_="glue-expansion-panel")

        countries = []
        for v in country_descriptions :
            country = v.find(class_='country-description').find('h1').getText().replace('\n','').strip()
            countries.append(country)

        US = soup.findAll(class_="glue-expansion-panel")[countries.index('United States')]
        US = US.find(class_="glue-expansion-panel-content")

        return US

    def scrape_normal(self,url) :
    
        ## Save and convert file to html
        ################################
        myfile = requests.get(url)
        open(self.tmp_file, 'wb').write(myfile.content)
        html = self.convert_pdf_to_html(self.tmp_file)
        ################################
        soup = BeautifulSoup(html, 'html.parser')
        
        inds_county = [i-1 for i,a in enumerate(soup.findAll('div')) if 'Retail & recreation' in a.getText()]
        
        print('\n{} counties'.format(len(inds_county)))

        to_fill = {}
        for i in range(len(inds_county)-1): 
            #print(i,end=',')
            observe = soup.findAll('div')[inds_county[i]:inds_county[i+1]]
            county = observe[0].getText().replace('\n','').replace('*','')
            to_fill[county] = []
            for item in observe[1:] :
                if len(to_fill[county]) == 6 :
                    continue
                if 'compared to baseline' in item.getText() :
                    to_fill[county].append(item.getText().replace('\n','').replace('*','').split(' ')[0])
                elif 'Not enough data for this date' in item.getText() :
                    to_fill[county].append(np.nan)
        return to_fill

    def scrape_DC(self,url) :
        ## Save and convert file to html
        ################################
        myfile = requests.get(url)
        open(self.tmp_file, 'wb').write(myfile.content)
        html = self.convert_pdf_to_html(self.tmp_file,skip_first=False)
        ################################
        soup = BeautifulSoup(html, 'html.parser')
        
        inds = [i-1 for i,a in enumerate(soup.findAll('div')) if 'compared to baseline' in a.getText()]
        
        print('\n1 county')
        
        to_fill = {'District of Columbia':[soup.findAll('div')[i].getText().replace('\n','') for i in inds]}
        
        return to_fill

    def scrape_counties(self,pages=None) :

        headers = ['Retail_Recreation','Grocery_Pharmacy','Parks','Transit','Workplace','Residential']

        df_create = pd.DataFrame()

        for state in self.US_html.findAll(class_="region-row glue-filter-result__item glue-filter-is-matching") :
            state_name = state.find('h1').getText().replace('\n','').strip()
            print(state_name)
            pdf_url = state.find('a')['href']
            
            if state_name == 'District of Columbia' :
                to_fill = self.scrape_DC(pdf_url)
            else :
                to_fill = self.scrape_normal(pdf_url)

            out = pd.DataFrame(to_fill).transpose()
            out.columns = headers
            out.reset_index(level=0, inplace=True)
            out.rename(columns={'index':'County'},inplace=True)
            out['State'] = state_name
            df_create = df_create.append(out)
        
        os.remove(self.tmp_file)

        return df_create
