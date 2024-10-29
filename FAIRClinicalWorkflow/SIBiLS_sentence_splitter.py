"""
    Version 2022, Oct.
"""

import re

"""
Abr. 2 char + dot in OTT terminology
['sp.', 'cf.', 'bv.', "'P.", 'pp.', '5.2', '5.4', '1.8', '1.1', '1.2', '1.5', '2.2', '3.3', 'al.', '4.3', 'No.', 'no.', '4.2', 'si.', '8.9', '6.8', '2.4', '5.5', '5.9', '6.5', '9.4', 'pv.', '6.7', '8.1', '9.2', '7.5', '8.2', 'Z.H', '4.7', '4.6', '7.8', '5.1', '9.1', '9.5', '7.6', '4.1', '6.2', '8.5', '3.1', '5.7', 'SP.', '4.5', 'Ca.', '2.5', '6.1', 'ap.', '3.2', '1.7', '3.5', '3.4', '2.1', '6.9', '9.3', '9.6', '8.3', '(U.', '7.7', 'sv.', '8.6', '4.4', '2.3', '5.3', '5.6', '8.4', '7.1', '7.2', '1.3', '1.4', '6.3', '6.4', 'St.', '2.7', '2.9', '2.8', '5.8', '3.6', '6.6', '2.6', '8.7', '3.7', '1.6', 'V.6', '(R.', 'Se.', 'nr.', 'Is.', '7.9', 'Z.h', 'N.8', 'M.A', "'K.", '9.9', '9.8', 'XI.', 'IV.', 'Sp.', "'A.", 'fo.', 'Ch.', 'st.', "'J.", '78.', 'cv.', 'II.', 'XV.', '1.9', 'R.3', 'R.8', 'R.4', 'R.5', "'H.", '3.9', '3.8', '5.0', '3.0', '4.0', '2.0', 'I.3', 'Ph.', 'D.,', '(A.', 'ex.', '(i.', 's.)', 'so.', '0.1', 'gr.', 'L.,', 'Mt.', 'DC.', "L.'", 'CL.', "'E.", 'f.)', '(D.', 's.n', '(P.', 'et.', 'a.l', 'Sw.', '(S.', 'Al.', 'M.8', '(C.', '(K.', '(N.', '1.B', '(T.', '9.c', '7.b', '5.a', '(W.', '0.0', '(Q.', "'T.", 'Sm.', '"C.', 'H.3', '4.8', '(E.',
"'C.", 'S.L', '8.d', "'S.", 'kl.', 'Ft.', "'G.", 'F.1', "'n.", 'ag.', '08.', '(n.', 'ca.', '(s.', 'pr.', '1.r', '7.r', '6.l', 'cl.']
Filtering (del dupplicate and case):
['sp.', 'cf.', 'bv.', 'pp.', 'al.', 'no.', 'si.', 'pv.', 'ap.', 'sv.', 'Se.', 'nr.', 'Is.', 'XI.', 'IV.', 'fo.', 'Ch.', 'st.', 'cv.', 'II.', 'XV.', 'Ph.', 'ex.', 'so.', 'gr.', 'Mt.', 'DC.', 'et.', 'Sw.', 'Sm.', 'kl.', 'Ft.', 'ag.', 'ca.', 'pr.', 'cl.']

Abr. 2 char + dot in NCBI full terminology
['sp.', 'bv.', 'al.', 'pv.', 'sv.', 'No.', '2.2', 'cv.', 'L.,', 'cf.', '1.2', '1.1', 'St.', 'ST.', 'SP.', '3.3', 'kl.', 'nr.', 'Sm.', '(K.', "'J.", 'DC.', '2.1', 'no.', '8.2', 'Mt.', '3.5', '3.4', '7.6', '7.9', '7.7', 'H.3', '4.5', '5.1', '4.2', "'S.", 'D.,', 'Ca.', '9.1', '2.7', '2.9', '4.3', '(U.', 'st.', 'f.)', '1.0', '6.2', '6.3', '7.2', 'V.6', '4.7', '4.1', '4.4', '(A.', '3.7', '5.2', 'cl.', '2.8', '5.3', '5.5', '5.7', '5.8', '1.7', '2.4', 'gr.', "'C.", '8.1', '3.1', '7.1', 'pr.', 'Is.', '3.8', '1.5', '6.4', '6.5', '6.6', '1.3', '1.4', '1.6', '0.1', '6.1', '9.2', '9.3', 'Se.', '9.9', '9.8', '9.4', '9.5', '9.6', '8.3', '8.6', 'Sw.', '7.5', 'F.1', '6.8', '5.9', '(R.', '3.2', 'XI.', 'IV.', '8.9', '1.r', '6.l', '7.r', '2.6', '4.6', '2.0', '3.0', '4.0', '5.0', '7.8', '8.5', '8.4', 'ag.', '1.8', '1.9', 'XV.', '2.3', 'Ft.', '2.5', '(n.', '5.6', '6.7', '8.7', '3.6', '4.8', '(s.', 's.)', 'I.3', '3.9', '(P.', "'K.", 'Sp.', 'II.', 'R.3', 'R.4', 'R.5', 'R.8', "'P.", 'pp.', 'CL.', 'et.', '5.4', 'fo.', 'Ph.', "'H.", 'a.l', '(E.', '"C.', 'so.', 'Z.h', '(D.', 'I.1', 'I.2', 'M.A', 'S.L', "'G.", 'Al.', '6.9', '(N.', '[J.', 'Z.H', '0.0', '5.a', '7.b',
'9.c', '8.d', "'T.", '(i.', 'si.', '1.B', 's.n', '(S.', 'ap.', 'N.8', '78.', '(Q.', 'M.8', '(T.', '08.', "'n.", 'Ch.', 'ca.', "'E.", 'M.5', "'A.", 's.p', "'1.", "'2.", "'3.", "'4.", 'ab.', 'NO.', 'Cu.']
Filtering (del dupplicate and case, keep only two letters min.):
['sp.', 'bv.', 'al.', 'pv.', 'sv.', 'cv.', 'cf.', 'kl.', 'nr.', 'Sm.', 'DC.', 'no.', 'Mt.', 'st.', 'cl.', 'gr.', 'pr.', 'Is.','Se.', 'Sw.', 'XI.', 'IV.', 'ag.', 'XV.', 'Ft.', 'II.', 'pp.', 'et.', 'fo.', 'Ph.', 'so.', 'si.', 'ap.', 'Ch.', 'ca.', 'ab.', 'Cu.']

Merge:
['sp.', 'cf.', 'bv.', 'pp.', 'al.', 'No.', 'si.', 'pv.', 'ap.', 'sv.', 'Se.', 'nr.', 'Is.', 'XI.', 'IV.', 'fo.', 'Ch.', 'st.', 'cv.', 'II.', 'XV.', 'Ph.', 'ex.', 'so.', 'gr.', 'Mt.', 'DC.', 'et.', 'Sw.', 'Sm.', 'kl.', 'Ft.', 'ag.', 'ca.', 'pr.', 'cl.']
['ab.', 'Cu.']

"""


SENTENCE_ENDERS_1ST_ROUND = re.compile(r"""
    # Split sentences on whitespace between them.
    (?:               # Group for two positive lookbehinds.
        (?<=[.!?])      # Either an end of sentence punct,
    |   (?<=[.!?]['"])  # or end of sentence punct and quote.
    )# End group of two positive lookbehinds.
    (?<!  Dr\.   )    # Don't end sentence on "Dr."
    (?<!  Fig\.   )   # Don't end sentence on "Fig."
    (?<!  Jr\.   )    # Don't end sentence on "Jr."
    (?<!  Mr\.   )    # Don't end sentence on "Mr.""
    (?<!  Mrs\.  )    # Don't end sentence on "Mrs."
    (?<!  Prof\. )    # Don't end sentence on "Prof."
    (?<!  Tab\.   )   # Don't end sentence on "Tab."
    (?<!  s\.p\. )    # Don't end sentence on "s.p."
    (?<!  subsp\.   ) # Don't end sentence on "subsp."
    (?<!  Sr\.   )    # Don't end sentence on "Sr."
    # Exception for one letter plus dot.
    (?<!  ^\w\.)     # ^ start of string, \w equivalent to [a-zA-Z0-9_], \. for point --> Don't end sentence with one letter and . (for E. coli case ar the beginning of sentence or in title)
    (?<!  \s\w\.)     # ^ start of string, \w equivalent to [a-zA-Z0-9_], \. for point --> Don't end sentence with one letter and . (for E. coli case ar the beginning of sentence or in title)
    # Exception for common small abreviations of two/three letters in combination with dot.
    (?<!  e\.g\.   )  # Don't end sentence on "e.g."
    (?<!  i\.c\.   )  # Don't end sentence on "i.c."
    (?<!  i\.d\.   )  # Don't end sentence on "i.d."
    (?<!  i\.e\.   )  # Don't end sentence on "i.e."
    (?<!  i\.m\.   )  # Don't end sentence on "i.m."
    (?<!  i\.q\.   )  # Don't end sentence on "i.q."
    (?<!  i\.v\.   )  # Don't end sentence on "i.v."
    (?<!  m\.p\.   )  # Don't end sentence on "m.p."
    (?<!  o\.d\.   )  # Don't end sentence on "o.d."
    (?<!  o\.h\.   )  # Don't end sentence on "o.h."
    (?<!  o\.m\.   )  # Don't end sentence on "o.m."
    (?<!  o\.n\.   )  # Don't end sentence on "o.n."
    (?<!  o\.s\.   )  # Don't end sentence on "o.s."
    (?<!  p\.c\.   )  # Don't end sentence on "p.c."
    (?<!  p\.i\.   )  # Don't end sentence on "p.i."
    (?<!  q\.d\.   )  # Don't end sentence on "q.d."
    (?<!  q\.h\.   )  # Don't end sentence on "q.h."
    (?<!  q\.l\.   )  # Don't end sentence on "q.l."
    (?<!  q\.n\.   )  # Don't end sentence on "q.n."
    (?<!  q\.p\.   )  # Don't end sentence on "q.p."
    (?<!  q\.q\.h\.   )  # Don't end sentence on "q.q.h."
    (?<!  q\.s\.   )  # Don't end sentence on "q.s."
    (?<!  q\.v\.   )  # Don't end sentence on "q.v."
    # Exceptions from OTT and NCBI Full Taxonomies
    (?<!  \sab\.)
    (?<!  \sal\.)
    (?<!  \sap\.) 
    (?<!  \sag\.) 
    (?<!  \sbv\.)
    (?<!  \sca\.)
    (?<!  \scf\.)
    (?<!  \sch\.)  
    (?<!  \scl\.) 
    (?<!  \scu\.) 
    (?<!  \scv\.)
    (?<!  \sdc\.)  
    (?<!  \set\.)
    (?<!  \sex\.) 
    (?<!  \sfo\.)
    (?<!  \sft\.)
    (?<!  \sgr\.) 
    (?<!  \skl\.) 
    (?<!  \smt\.) 
    (?<!  \sno\.)
    (?<!  \snr\.) 
    (?<!  \spp\.)
    (?<!  \spr\.)
    (?<!  \sps\.)
    (?<!  \spv\.)
    (?<!  \sse\.)  
    (?<!  \ssi\.)
    (?<!  \ssm\.) 
    (?<!  \sso\.)  
    (?<!  \ssp\.)
    (?<!  \sst\.)     
    (?<!  \ssv\.)  
    (?<!  \ssw\.)  
    (?<!  II\.) 
    (?<!  IV\.) 
    (?<!  XI\.) 
    (?<!  XV\.) 
    \s+               # Split on whitespace between sentences.
    """, re.IGNORECASE | re.VERBOSE)


def sentence_split(text):
    return [
        sentence.strip()
        for sentence in SENTENCE_ENDERS_1ST_ROUND.split(text)  
    ]
