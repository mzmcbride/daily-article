#! /usr/bin/env python
# Public domain; Mr.Z-man, MZMcBride; 2012

import datetime
from email.MIMENonMultipart import MIMENonMultipart
import htmlentitydefs
import urllib
import re
import smtplib
import textwrap

import BeautifulSoup
import wikitools

import config

# Establish a few wikis
enwiki_base = 'https://en.wikipedia.org'
enwiki = wikitools.Wiki(enwiki_base+'/w/api.php'); enwiki.setMaxlag(-1)
enwikt_base = 'https://en.wiktionary.org'
enwikt = wikitools.Wiki(enwikt_base+'/w/api.php'); enwikt.setMaxlag(-1)
enquote_base = 'https://en.wikiquote.org'
enquote = wikitools.Wiki(enquote_base+'/w/api.php'); enquote.setMaxlag(-1)

# Figure out the date
date = datetime.date.today()
year = date.year
day = date.day
month = date.strftime('%B')

# Empty list
final_sections = []

def strip_html(original_text):
    soup = BeautifulSoup.BeautifulSoup(original_text)
    new_text = ''.join(soup.findAll(text=True)).encode('utf-8')
    return new_text

def parse_wikitext(wiki, wikitext):
    params = {'action' : 'parse',
              'text'   : wikitext,
              'disablepp' : 'true'}
    req = wikitools.api.APIRequest(wiki, params)
    response = req.query()
    parsed_wikitext = response[u'parse'][u'text'][u'*']
    return parsed_wikitext

def unescape(text):
    def fixup(m):
        text = m.group(0)
        if text[:2] == '&#':
            # character reference
            try:
                if text[:3] == '&#x':
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        return text # leave as is
    return re.sub('&#?\w+;', fixup, text)

def make_featured_article_section(month, day, year):
    page_title = '%s/%s %s, %s' % ("Wikipedia:Today's featured article",
                                   month,
                                   day,
                                   year)
    try:
        wikitext = wikitools.Page(enwiki, page_title).getWikiText()
    except wikitools.page.NoPage:
        return False
    parsed_wikitext = parse_wikitext(enwiki, wikitext)
    # Grab the first <p> tag and pray
    found = False
    for line in parsed_wikitext.split('\n'):
        if line.startswith('<p>') and not found:
            first_para = line
            found = True
    p_text = first_para.rsplit('. (', 1)[0]+'.'
    p_text = unescape(p_text)
    clean_p_text = strip_html(p_text)
    more_html = first_para.rsplit('. (', 1)[1]
    more_soup = BeautifulSoup.BeautifulSoup(more_html)
    for a in more_soup.findAll('a'):
        read_more = ('%s' + '<%s%s>') % ('Read more: ',
                                         enwiki_base,
                                         a['href'].encode('utf-8'))
        featured_article_title = a['title'].encode('utf-8')
    featured_article_section = '\n'.join([wrap_text(clean_p_text),
                                          '',
                                          read_more,
                                          ''])
    final_sections.append(featured_article_section)
    return featured_article_title

def make_selected_anniversaries_section(month, day):
    page_title = 'Wikipedia:Selected anniversaries/%s %s' % (month, day)
    parsed_wikitext = parse_wikitext(enwiki, '{{'+page_title+'}}')
    anniversaries = []
    for line in parsed_wikitext.split('\n'):
        if line.startswith('<li'):
            line = line.replace(' <i>(pictured)</i> ', ' ')
            plaintext_lines = wrap_text(strip_html(unescape(line)))
            formatted_plaintext_lines = ':\n\n'.join(plaintext_lines.split(' \xe2\x80\x93 ', 1))
            line_soup = BeautifulSoup.BeautifulSoup(line)
            for b in line_soup.findAll('b'):
                for a in b.contents:
                    read_more = ('<%s%s>') % (enwiki_base,
                                              a['href'].encode('utf-8'))
            complete_item = formatted_plaintext_lines+'\n'+read_more+'\n'
            anniversaries.append(complete_item)
    header = '_______________________________\n'
    header += 'Today\'s selected anniversaries:\n'
    selected_anniversaries_section = '\n'.join([header,
                                                '\n'.join(anniversaries)])
    final_sections.append(selected_anniversaries_section)
    return

def make_wiktionary_section(month, day):
    page_title = 'Wiktionary:Word of the day/%s %s' % (month, day)
    parsed_wikitext = parse_wikitext(enwikt, '{{'+page_title+'}}')
    soup = BeautifulSoup.BeautifulSoup(parsed_wikitext)
    word = soup.find('span', id='WOTD-rss-title').string.encode('utf-8')
    definitions = []
    count = False
    if parsed_wikitext.count('<li') > 1:
        count = 1
    for line in parsed_wikitext.split('\n'):
        if line.startswith('<li'):
            clean_line = strip_html(line)
            if count:
                count_text = str(count)+'. '
                count += 1
            else:
                count_text = ''
            definitions.append(count_text+wrap_text(clean_line))
    header = '_____________________________\n'
    header += 'Wiktionary\'s word of the day:\n'
    read_more = '<'+enwikt_base+'/wiki/'+urllib.quote(word.replace(' ', '_'))+'>'
    wiktionary_section = '\n'.join([header,
                                    word+':',
                                    '\n'.join(definitions),
                                    read_more,
                                    ''])
    final_sections.append(wiktionary_section)
    return

def make_wikiquote_section(month, day, year):
    page_title = 'Wikiquote:Quote of the day/%s %s, %s' % (month, day, year)
    parsed_wikitext = parse_wikitext(enquote, '{{'+page_title+'}}')
    lines = []
    for line in parsed_wikitext.split('\n'):
        if line.find('~') != -1:
            author_soup = BeautifulSoup.BeautifulSoup(line)
            for a in author_soup.findAll('a'):
                read_more = ('<%s%s>') % (enquote_base,
                                          a['href'].encode('utf-8'))
                author = '  --'+a.string.encode('utf-8')
        else:
            lines.append(unescape(line))
    authorless_lines = '\n'.join(lines)
    quote = strip_html(authorless_lines)
    quote = quote.strip()
    header = '___________________________\n'
    header += 'Wikiquote quote of the day:\n'
    wikiquote_section = '\n'.join([header,
                                   wrap_text(quote),
                                   author,
                                   read_more])
    final_sections.append(wikiquote_section)
    return

def wrap_text(text):
    wrapped_lines = textwrap.wrap(text, width=72)
    return '\n'.join(wrapped_lines)

# Do some shit
featured_article_title = make_featured_article_section(month, day, year)
make_selected_anniversaries_section(month, day)
make_wiktionary_section(month, day)
make_wikiquote_section(month, day, year)

final_output = '\n'.join(final_sections)

# Okay now send an e-mail
subject = '%s %d: %s' % (month, day, featured_article_title)

fromaddr = config.fromaddr
toaddr = config.toaddr
msg = MIMENonMultipart('text', 'plain')
msg['Content-Transfer-Encoding'] = '8bit'
msg.set_payload(final_output, 'utf-8')
msg['From'] = fromaddr
msg['Subject'] = subject
server = smtplib.SMTP(config.smtphost, config.smtpport)
server.ehlo()
server.starttls()
server.ehlo()
server.login(config.fromaddr, config.emailpass)
for addr in toaddr:
    msg['To'] = addr
    body = msg.as_string()
    server.sendmail(fromaddr, addr, body, '8bitmime')
server.quit()
