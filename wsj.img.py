﻿# # # #!/usr/bin/python

import sys, re, os, shutil, traceback, json, platform
from bs4 import BeautifulSoup
from datetime import *
from urlparse import urlparse

from pyvin.spider import Spider, Persist, SpiderSoup
from pyvin.core import Log
from persist import WsjPersist

reload(sys)
sys.setdefaultencoding('utf8')

page_charset = 'GB2312'


def dateFromStr(strDate = '', strFmt='%Y%m%d'):
    try:
        ddTT = datetime.strptime(strDate, strFmt)
        dd = ddTT.date()
        return dd
    except:
        print 'invalid date string %s ' % strDate
        traceback.print_exc()

def checkDate(strDate, strStart='', strEnd=''):
    # print 'date: [%s]' % strDate
    # print 'strStart: [%s]' % strStart
    # print 'strEnd: [%s]' % strEnd
    if len(strStart) > 0:
        dStart = dateFromStr(strStart)
    else:
        dStart = date.min

    # until today
    if len(strEnd) > 0:
        dEnd = dateFromStr(strEnd)
    else:
        dEnd = date.today()

    dDate = dateFromStr(strDate)
    return (dDate >= dStart and dDate <= dEnd)

def parseUrl(url):
    url = urlparse(url)
    segs = url.path.split('/')
    return segs

class WsjImg:
    site_root = 'http://cn.wsj.com/'
    page_root = 'http://cn.wsj.com/gb/'
    img_root = 'http://cn.wsj.com/pictures/photo/'
    starts = ['http://cn.wsj.com/gb/pho.asp']
    # starts = ['http://cn.wsj.com/gb/20141230/PHO094555.asp']
    # callbacks = {'http://cn.wsj.com/gb/pho.asp':WsjImg.find_links, 'http://cn.wsj.com/gb/':WsjImg.parse_page, 'http://cn.wsj.com/pictures/photo/':WsjImg.save_img}

    # page url path
    # ['', 'gb', '20130528', 'PHO184538.asp']
    idx_page_date = 2
    idx_page_filename = 3
    # img url path
    # ['', 'pictures', 'photo', 'BJ20141226094555', '01.jpg']
    idx_img_dir = 3
    idx_img_filename = 4

    # persist
    DIR_BASE = 'base'
    DIR_ROOT = 'dat'
    DIR_IMG = 'img'

    def __init__(self, start='', end=''):
        self.TAG = WsjImg.__name__
        self.init_date(start, end)
        self.db = WsjPersist()

        self.callbacks = {
                'http://cn.wsj.com/gb/pho.asp': self.find_links, 
                'http://cn.wsj.com/gb/20': self.parse_page,
                'http://cn.wsj.com/pictures/photo/': self.save_img
        }
        self.spider = Spider('WsjImg')
        self.spider.set_proxy('proxy-amer.delphiauto.net:8080', 'rzfwch', '8ik,mju7')
        self.spider.add_callbacks(self.callbacks)
        self.spider.add_urls(self.starts)
        self.spider.start()

    def init_date(self, strStart='', strEnd=''):
        '''Initiate start/end date'''
        self.strStart = strStart
        self.strEnd = strEnd

    def find_links(self, url, response):
        '''Parse the photos news default page and find photos news page urls'''
        Log.i(self.TAG, 'find links in %s' % url)
        links = ImgPageLinks(response, self.strStart, self.strEnd)
        urls = links.getLinks(response)
        # urls = links.persistToDB(self.db)
        self.spider.add_urls(urls)

    def parse_page(self, url, response):
        '''Parse photos news page, find content and image urls, also with other photos news page urls.'''
        # find img page links
        self.find_links(url, response)
        # process image page.
        imgPage = ImgPage(url, response)
        imgPage.clear()
        imgPage.parseImgUrls()
        if len(imgPage.imgUrls.keys()) > 1:
            imgPage.save(os.path.join(WsjImg.DIR_ROOT, imgPage.filePath))

            with open(os.path.join(WsjImg.DIR_ROOT, imgPage.data['path']), 'w') as f:
                f.write(json.dumps(imgPage.data))

            imgPage.persistToDB(self.db)
            self.db.updateArt(url, imgPage.title, imgPage.summary)

            # save imgs of the page
            self.save_imgs(imgPage)

            # copy base files to here
            # os.system('cp -a %s/* %s/' % (WsjImg.dir_base, os.path.join(WsjImg.dir_root, page_date)))

            self.spider.fetch.copyall(WsjImg.DIR_BASE, os.path.join(WsjImg.DIR_ROOT, imgPage.pageDate))
        else:
            print 'no link find in %s' % url

    def save_img(self, url, response):
        print 'ignore %s' % url

    def save_imgs(self, imgPage):
        for url in imgPage.imgUrls.keys():
            dstfile = os.path.join(WsjImg.DIR_ROOT, imgPage.imgUrls[url]['path'])
            self.spider.download(url, dstfile)

class ImgPageLinks:
    '''Find photos news page urls'''
    KEY_URL = 'url'
    KEY_DATE = 'date'

    def __init__(self, page, strStart, strEnd):
        print '[ImgPageLinks]'
        # self.soup = BeautifulSoup(page, from_encoding=page_charset)
        self.strStart = strStart
        self.strEnd = strEnd
        self.links = {}

    def getLinks(self, html):
        # 'http://cn.wsj.com/gb/20130528/PHO184538.asp'
        p = re.compile('\d{4}\d{2}\d{2}/PHO\d{6}.asp');
        urls = p.findall(html)
        # unique urls
        for url in urls:
            self.links[url] = url

        # check date and correct links
        p = re.compile('\d{4}\d{2}\d{2}');
        for url in self.links.keys():
            strDate = p.findall(url)[0]
            # print strDate
            del(self.links[url])
            if (checkDate(strDate, self.strStart, self.strEnd)):
                url = '%s%s' % (WsjImg.page_root, url)
                self.links[url] = {}
                self.links[url][ImgPageLinks.KEY_DATE] = strDate
                self.links[url][ImgPageLinks.KEY_URL] = url
            else:
                print 'skip %s' % url
        # print self.links
        return self.links.keys()

    def persistToDB(self, db):
        '''add self.links to db, return new added link list'''
        for url in self.links.keys():
            ret = db.addArt(self.links[url][ImgPageLinks.KEY_URL], self.links[url][ImgPageLinks.KEY_DATE])
            ret = db.isArtDownload(url)
            if ret:
                del(self.links[url])
        return self.links.keys()

class ImgPage:
    '''Parse photos news page, get content and image urls'''
    def __init__(self, url, page):
        print '[ImgPage]'
        print url
        # print page
        self.url = url
        self.soup = BeautifulSoup(page, "html5lib", from_encoding=page_charset)
        self.title = self.soup.title.text
        self.summary = ''
        self.imgUrls = {}

        segs = parseUrl(url)
        self.pageDate = segs[WsjImg.idx_page_date]
        self.filePath = os.path.join(self.pageDate, "%s-%s" % (self.title, segs[WsjImg.idx_page_filename].replace('.asp', '.html')))

        # create a data object for data exchange
        self.data = {}
        self.data['path'] = os.path.join(self.pageDate, segs[WsjImg.idx_page_filename].replace('.asp', '.json'))
        self.data['url'] = url
        self.data['title'] = self.title
        self.data['summary'] = self.summary
        self.data['date'] = self.pageDate
        self.data['imgs'] = []


    # after clear, find image urls
    ## orignal link in html: '../../pictures/photo/BJ20141226094555/01.jpg'
    def parseImgUrls(self):
        # print 'parseImgUrls'
        img_nodes = self.soup.findAll('img')
        for item in img_nodes:
            url = item['src']
            if url:
                # print url
                # change img src to local relative path.
                item['src'] = url.replace('../../pictures/photo', WsjImg.DIR_IMG)
                # save url for download
                url = url.replace('../../pictures/photo/', 'http://cn.wsj.com/pictures/photo/')
                if url.startswith('http://cn.wsj.com/pictures/photo/'):
                    self.imgUrls[url] = {}
                    self.imgUrls[url]['url'] = url
                    self.imgUrls[url]['alt'] = item['alt']
                    segs = parseUrl(url)
                    self.imgUrls[url]['path'] = os.path.join(self.pageDate, WsjImg.DIR_IMG, segs[WsjImg.idx_img_dir], segs[WsjImg.idx_img_filename])
                    self.imgUrls[url]['src'] = os.path.join(WsjImg.DIR_IMG, segs[WsjImg.idx_img_dir], segs[WsjImg.idx_img_filename])
                    self.data['imgs'].append(self.imgUrls[url])
        return self.imgUrls.keys()

    # clear no used tags
    def clear(self):
        # find summary
        # print 'clear'
        summary = self.soup.findAll('div', attrs={'id':'summary'})
        if len(summary) > 0:
            # print summary
            self.summary = summary[0].text
            # print self.summary
            self.data['summary'] = self.summary

        # find imgs
        divTs = self.soup.findAll('div', attrs={'id': 'sliderBox'})

        # clear
        self.soup.body.clear()
        del self.soup.body['onload']
        SpiderSoup.clearNode(self.soup, 'script')
        SpiderSoup.clearNode(self.soup, 'noscript')
        SpiderSoup.clearNode(self.soup, 'style')
        SpiderSoup.clearNode(self.soup, 'link')
        SpiderSoup.clearNode(self.soup, 'meta', {'name': 'keywords'})
        SpiderSoup.clearNode(self.soup, 'meta', {'name': 'description'})
        # set css
        SpiderSoup.insertCss(self.soup, "css/jquery.mobile-1.4.5.min.css")
        SpiderSoup.insertCss(self.soup, "css/swipebox.css")
        SpiderSoup.insertCss(self.soup, "css/wsj.img.css")
        # set script
        SpiderSoup.insertScript(self.soup, "js/jquery-2.1.3.min.js")
        SpiderSoup.insertScript(self.soup, "js/jquery.mobile-1.4.5.min.js")
        SpiderSoup.insertScript(self.soup, "js/jquery.swipebox.js")
        SpiderSoup.insertScript(self.soup, "js/wsj.img.js")

        # add ul
        ul_tag = self.soup.new_tag("ul")
        ul_tag['data-role'] = 'listview'
        self.soup.body.append(ul_tag)

        # add imgs list
        if len(divTs) > 0:
            divT = divTs[0]
            liTs = divT.findAll('li')
            for liT in liTs:
                ul_tag.append(liT)

        # set img class as swipebox
        img_nodes = self.soup.findAll('img')
        for item in img_nodes:
            item['class'] = 'swipebox'

        return str(self.soup)

    def save(self, filename):
        per = Persist(filename)
        per.store_soup(self.soup)
        per.close()

    def persistToDB(self, db):
        id = db.getArtIdByUrl(self.url)
        if len(self.imgUrls) > 0:
            for url in self.imgUrls.keys():
                db.addPic(id, self.imgUrls[url]['url'], self.imgUrls[url]['src'], self.imgUrls[url]['alt'])
        db.setArtDownload(self.url)

if __name__ == "__main__":
    # print 'wsjimg'

    sStart = ''
    sEnd = ''
    argc = len(sys.argv)
    if (argc == 2):
        sStart = sys.argv[1]
    elif (argc == 3):
        sStart = sys.argv[1]
        sEnd = sys.argv[2]

    print "get [%s ~ %s]" % (sStart, sEnd)

    wsj = WsjImg(start=sStart, end=sEnd)
