import os
import re
import json
import zipfile
import datetime
import warnings
from bs4 import BeautifulSoup
import requests
from PyPDF2 import PdfFileMerger

header = {
    "User-Agent": "PostmanRuntime/7.20.1",
    "Accept": "*/*",
    "Cache-Control": "no-cache",
    "Postman-Token": "8eb5df70-4da6-4ba1-a9dd-e68880316cd9,30ac79fa-969b-4a24-8035-26ad1a2650e1",
    "Host": "medianet.edmond-de-rothschild.fr",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "cache-control": "no-cache",
}

class Day:
    NOW = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    YEAR = str(NOW.year).zfill(4)
    MONTH = str(NOW.month).zfill(2)
    DAY = str(NOW.day).zfill(2)
    DATE = ''.join([YEAR, MONTH, DAY])

    DIR = os.path.join('Download', DATE)
    PAGES_FILE_PATH = os.path.join(DIR, f'证券时报{DATE}.zip')
    MERGED_FILE_PATH = os.path.join(DIR, f'证券时报{DATE}.pdf')

    HOME_URL = f'http://epaper.stcn.com/paper/zqsb/html/{YEAR}-{MONTH}/{DAY}/node_2.htm'

    HOME_CONTENT = requests.get(HOME_URL)
    if HOME_CONTENT.encoding == 'ISO-8859-1':
        encodings = requests.utils.get_encodings_from_content(HOME_CONTENT.text)
        if encodings:
            encoding = encodings[0]
        else:
            encoding = HOME_CONTENT.apparent_encoding

        HOME_CONTENT = HOME_CONTENT.content.decode(encoding, 'replace') #如果设置为replace，则会用?取代非法字符
	
    # print(HOME_CONTENT)
    PAGE_LIST = re.findall(f'<dt id="....">', HOME_CONTENT)
    PAGE_LIST = [item[-6:-2] for item in PAGE_LIST]
    print(PAGE_LIST)

    if len(PAGE_LIST)==0:
        PAGE_LIST = re.findall(f'<dt id=....>', HOME_CONTENT)
        PAGE_LIST = [item[-5:-1] for item in PAGE_LIST]
        print(PAGE_LIST)

    if (PAGE_LIST == []):
        print("Stopped")
        raise SystemExit(0)
        
    PAGE_NAME_LIST = re.findall('版<i>(.*?)</i>', HOME_CONTENT)
    TOTAL_COUNT = int(re.findall(r'\d+',PAGE_NAME_LIST[0])[0])

    ADJ_PAGE_LIST = []
    ADJ_PAGE_NAME_LIST = []
    for i in range(len(PAGE_NAME_LIST)):
        if PAGE_NAME_LIST[i] != "信息披露":
            ADJ_PAGE_LIST.append(PAGE_LIST[i])
            ADJ_PAGE_NAME_LIST.append(PAGE_NAME_LIST[i])

    PAGE_COUNT = len(ADJ_PAGE_LIST)
    print(PAGE_COUNT)

    soup = BeautifulSoup(HOME_CONTENT, "html.parser")
    PAGES_CONTENT = [str(tag.dd) for tag in soup.find_all("dl")]

    if not os.path.isdir(DIR):
        os.makedirs(DIR)

class Page:
    def __init__(self, HOME_CONTENT, name, page_content, page: str):
        self.page = page
        self.name = "第" + self.page + "版: " + name
        self.html_url = f'http://epaper.stcn.com/paper/zqsb/html/{Day.YEAR}-{Day.MONTH}/{Day.DAY}/node_2.htm'
        self.html = HOME_CONTENT
        self.page_content = page_content
        self.pdf = requests.get(
            (
                'http://epaper.stcn.com/paper/zqsb/page/1/{0}-{1}/{2}/{3}/{0}{1}{2}{3}_pdf.pdf'
                    .format(Day.YEAR, Day.MONTH, Day.DAY, page)
            ), header
        ).content
        self.path = os.path.join(Day.DIR, f'{self.page}.pdf')

    def __str__(self) -> str:
        return (
            f'{self.__class__.__name__}'
            f'[date={Day.DATE}, page={self.page}]'
        )

    def __repr__(self) -> str:
        return self.__str__()

    @property
    def title(self):
        return self.name

    @property
    def articles(self):
        output_article_list = []
        html_components = re.findall(f'content_........htm', self.page_content)
        article_titles = re.findall(f'.htm">(.*?)</a></li>', self.page_content)
        for i in range(len(html_components)):
            article_html = 'http://epaper.stcn.com/paper/zqsb/html/{}-{}/{}/{}'.format(Day.YEAR, Day.MONTH, Day.DAY, html_components[i])
            output_article_list.append((article_html, article_titles[i]))
        return output_article_list

    def save_pdf(self):
        with open(self.path, 'wb') as f:
            f.write(self.pdf)


def main():
    warnings.filterwarnings('ignore')
    pages = [Page(Day.HOME_CONTENT, Day.ADJ_PAGE_NAME_LIST[idx], Day.PAGES_CONTENT[idx], page_str) for idx, page_str in enumerate(Day.ADJ_PAGE_LIST)]
    pages_file = zipfile.ZipFile(Day.PAGES_FILE_PATH, 'w')
    merged_file = PdfFileMerger(False)
    data = {
        'date': Day.DATE,
        'page_count': str(Day.PAGE_COUNT),
        'pages_file_path': Day.PAGES_FILE_PATH,
        'merged_file_path': Day.MERGED_FILE_PATH,
        'release_body': (
            f'# [{Day.DATE}]({Day.HOME_URL})'
            f'\n\n今日 {Day.TOTAL_COUNT} 版'
        )
    }
    
    # Process
    for page in pages:
        # Save pdf
        page.save_pdf()

        # Pages file
        pages_file.write(page.path, os.path.basename(page.path))

        # Merged file
        merged_file.append(page.path)

        # Data
        data['release_body'] += f'\n\n## [{page.title}]({page.html_url})\n'
        for article in page.articles:
            data['release_body'] += f'\n- [{article[1]}]({article[0]})'

        # Info
        print(f'Processed {page}')

    # Save
    # pages_file.close()
    merged_file.write(Day.MERGED_FILE_PATH)
    merged_file.close()
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

if __name__ == '__main__':
    main()
