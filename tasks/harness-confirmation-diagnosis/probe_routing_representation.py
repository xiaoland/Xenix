"""Fixed, training-only grouped CV and representation probes; no oracle-based fitting."""
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold

from xenix.services.data_tokenization_contracts import TextPreparationInput
import xenix.services.ml.text_preparation as preparation

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT/'tests/e2e/agent_harness/fixtures/business_tasks/routing'
history = pd.read_csv(FIXTURES/'confirmation/history.csv')
new = {name:pd.read_csv(FIXTURES/name/'new_tickets.csv') for name in ['standard','confirmation']}
truth = {name:json.loads((FIXTURES/name/'oracle.json').read_text(encoding='utf8'))['labels'] for name in new}
preparer = preparation.build_text_preparer(TextPreparationInput())
prepared = preparation.prepare_text_classification_data(history,text_column='message',target_column='queue',business_group_column='customer_batch',preparer=preparer)
original = preparation._tokenize_normalized

def preserving_cjk(normalized, *, tokenizer, stopwords):
    return [token for segment in tokenizer.lcut(normalized,HMM=False)
        for token in preparation._TOKEN_RE.findall(str(segment))
        if token not in stopwords and (len(token)>=2 or re.fullmatch(r'[\u3400-\u9fff]',token))]

experiments = []
for mode in ['current','keep_cjk_characters','character_ngrams']:
    preparation._tokenize_normalized = preserving_cjk if mode=='keep_cjk_characters' else original
    if mode=='character_ngrams':
        texts=history.message
        future={name:frame.message for name,frame in new.items()}
    else:
        texts=preparer.prepare_series(history.message).prepared_texts
        future={name:preparer.prepare_series(frame.message).prepared_texts for name,frame in new.items()}
    for min_df in [1,2]:
        def vectorizer():
            if mode=='character_ngrams':
                return TfidfVectorizer(analyzer='char',ngram_range=(2,4),min_df=min_df,max_features=5000)
            return TfidfVectorizer(tokenizer=str.split,preprocessor=None,token_pattern=None,lowercase=False,min_df=min_df,max_features=5000)
        def fit(train):
            vocab=vectorizer()
            model=LogisticRegression(class_weight='balanced',max_iter=500,random_state=42)
            model.fit(vocab.fit_transform(texts.iloc[train]),history.queue.iloc[train])
            return vocab,model
        folds=[]
        for train,test in GroupKFold(n_splits=5).split(texts,history.queue,prepared.connected_groups):
            vocab,model=fit(train)
            pred=model.predict(vocab.transform(texts.iloc[test]))
            folds.append({'correct':int(np.sum(pred==history.queue.iloc[test])),'total':len(test),'heldout_batches':sorted(history.customer_batch.iloc[test].unique().tolist())})
        vocab,model=fit(np.arange(len(history)))
        outcomes={}
        for name,values in future.items():
            pred=model.predict(vocab.transform(values))
            labels=[truth[name][ticket] for ticket in new[name].ticket_id]
            outcomes[name]={'correct':int(np.sum(pred==labels)),'total':len(labels),
                'errors':[ticket for ticket,p,y in zip(new[name].ticket_id,pred,labels) if p!=y]}
        experiments.append({'representation':mode,'min_df':min_df,'grouped_cv_correct':sum(f['correct'] for f in folds),
            'grouped_cv_total':90,'folds':folds,'deliveries':outcomes})
preparation._tokenize_normalized=original
result={'experiments':experiments,'evidence_limit':'Five fixed group folds use historical labels only. Representation alternatives are offline counterfactuals, not production fixes or a benchmark rerun; test truths score results after fitting.'}
(Path(__file__).parent/'routing-representation-probes.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
for row in experiments:
    print(row['representation'],row['min_df'],row['grouped_cv_correct'],{k:v['correct'] for k,v in row['deliveries'].items()})
