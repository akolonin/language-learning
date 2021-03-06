# language-learning/src/grammar_inducer.py                              # 81207
from copy import deepcopy
from collections import Counter
from typing import List, Tuple
from .utl import UTC, kwa


def add_disjuncts(cats, links, **kwargs):  # copied from category_learner to update here
    # add disjuncts to categories {cats} after k-means or agglomerative clustering
    # cats: {'cluster': [], 'words': [], }
    # TODO?: add top disjuncts only ~ lines 135, 140-157, + prune disjuncts after clusters
        # OR def prune_cats?
    max_disjuncts = kwa(100000, 'max_disjuncts', **kwargs)
    verbose = kwa('none', 'verbose', **kwargs)

    fat_cats = deepcopy(cats)
    top_clusters = [i for i, x in enumerate(cats['cluster']) if i > 0 and x is not None]
    # word_clusters = {x:i for i,x in enumerate(top_clusters)}
    word_clusters = dict()  # TODO: ⇒ comprehension?
    for i in top_clusters:
        for word in cats['words'][i]:
            word_clusters[word] = i

    df = links.copy()
    df['cluster'] = df['word'].apply(lambda x: word_clusters[x] if x in word_clusters else 0)
    cdf = df.groupby('cluster').sum().reset_index()
    cdf = cdf.loc[cdf['cluster'] > 0]
    fat_cats['counts'] = [0] + cdf['count'].tolist()

    fat_cats['disjuncts'] = [[]]
    fat_cats['dj_counts'] = [[]]
    cdf = df.groupby(['cluster', 'link'], as_index=False).sum() \
            .sort_values(by=['cluster', 'count'], ascending=[True, False])

    # TODO: dj_counts = Counter()
    # ~ ddf = cdf.groupby('link', as_index=False).sum() \
    #             .sort_values(by='count', ascending=[False])
    # ~ dj_counts[tuple(dj)] += categories['dj_counts'][cluster][i]
    # top_djs = set([x[0] for x in dj_counts.most_common(max_disjuncts)])

    for cluster in top_clusters:
        ccdf = cdf.loc[cdf['cluster'] == cluster]
        fat_cats['disjuncts'].append(ccdf['link'].tolist())
        fat_cats['dj_counts'].append(ccdf['count'].tolist())

    fat_cats['djs'] = [[]]
    ldf = df[['link', 'count']].copy().groupby('link').sum().sort_values(by='count', ascending=False).reset_index()
    djdict = {x: i for i, x in enumerate(ldf['link'].tolist())}
    df.drop(['word'], axis=1, inplace=True)
    df['dj'] = df['link'].apply(lambda x: djdict[x])
    cdf = df.groupby(['cluster', 'dj'], as_index=False).sum().sort_values(by=['cluster', 'dj'], ascending=[True, True])
    for cluster in top_clusters:
        ccdf = cdf.loc[cdf['cluster'] == cluster]
        fat_cats['djs'].append(ccdf['dj'].tolist())

    return fat_cats


def prune_cats(categories, **kwargs):  # 81204 checked as check_cats -- smth wrong?
    # check each category has associated disjuncts, delete if no disjuncts
    # TODO: 1. check cats
    # TODO: 2. delete cats with empty disjunct set
    # TODO: 3. delete disjuncts with connectors linked to the deleted cats
    # TODO: loop 2-3
    # 81204 ad-hoc:  # nicht gut -- lost hierarchy, connectors to deleted clusters :(
    cats = {key: [] for key in categories.keys()}
    for i,djs in enumerate(cats['disjuncts']):
        if len(djs) > 0:
            for key in cats.keys():
                cats[key].append(categories[key][i])
            # if i < 3: print(i, 'cats:', cats)
        else:
            continue
    # print('cats[cluster]:', cats['cluster'])
    return cats, {'prune_cats': 'under construction'}


def check_cats(cats, **kwargs):
    print('check_cats - cats:', cats.keys())
    orphans = []
    for i,djs in enumerate(cats['disjuncts']):
        if len(djs) == 0:
            print(i, 'cluster:', cats['cluster'][i], 'words:', cats['words'][i], 'djs:', djs)
            orphans.append([i, cats['cluster'][i], cats['words'][i], djs])
    if len(orphans) > 0:
        print('orphans:', orphans)
    #else:
    return {'orphaned_clusters': orphans}


def induce_grammar(categories, **kwargs):                               # 81205
    # categories == {'cluster': [], 'words': [], ...}
    max_disjuncts = kwa(100000, 'max_disjuncts', **kwargs)              # 81105
    verbose = kwa('none', 'verbose', **kwargs)

    rules = deepcopy(categories)

    if verbose == 'debug':
        print('grammar_inducer.py line 99: rules.keys():\n',
              {key: len(rules[key]) for key in rules.keys()})

    dj_counts = Counter()                                               # 81105
    clusters = [i for i,x in enumerate(rules['cluster']) if i > 0 and x is not None]
    word_clusters = dict()
    for i in clusters:
        for word in rules['words'][i]:
            word_clusters[word] = i
    disjuncts = {}  # 81205

    for cluster in clusters:
        djs = []
        for i, rule in enumerate(categories['disjuncts'][cluster]):
            if type(rule) is str:  # 'a- & was-' ⇒ (-9,-26) + reverse 81012
                x = rule.split()
                lefts = []
                rights = []
                for y in x:
                    if (y not in ['&', ' ', '']) and (y[:-1] in word_clusters):
                        if y[-1] == '+':
                            rights.append(word_clusters[y[:-1]])
                        elif y[-1] == '-':
                            lefts.append(-1 * word_clusters[y[:-1]])
                        else:
                            print('no sign?', y, 'in', x)  # TODO:ERROR?
                lefts.reverse()  # 81012
                dj = lefts + rights
                if len(dj) > 0:
                    djs.append(tuple(dj))
                    dj_counts[tuple(dj)] += categories['dj_counts'][cluster][i]
                if verbose == 'debug':
                    print(f'induce_grammar_: cluster {cluster}: {rule} ⇒ {tuple(dj)}')
            # TODO? +elif type(rule) is tuple? connectors - tuples?
        rules['disjuncts'][cluster] = set(djs)
        #? disjuncts[cluster] = set(djs)

    # TODO: move this code to prune_cats and call it before induce_grammar
    # Add only top-frequency disjuncts:                                 # 81105
    top_djs = set([x[0] for x in dj_counts.most_common(max_disjuncts)])
    pruned_clusters = []   # 81206
    pruned_words = []   # 81206
    trace = []          # 81205 track orphaned rules
    clusters = [x for i,x in enumerate(rules['cluster']) if i > 0 and x is not None]
    for cluster in clusters:  # 81105 added -- blocked 81205
        # rules['disjuncts'][cluster] = top_djs & rules['disjuncts'][cluster]
        # - blocked 81205 -- might create rule without disjuncts ⇒ Link Grammar error
        # FIXME: add only rules with checked len(disjuncts) > 0
        i = rules['cluster'].index(cluster)
        djs = top_djs & rules['disjuncts'][i]
        #print('cluster:', cluster, '- line #', i, '-',
        #      len(rules['disjuncts'][i]), 'disjuncts,', len(djs), 'top_djs')
        if len(djs) > 0:
            rules['disjuncts'][i] = djs
        else:  # TODO: pop rules[...][i]
            #rules['disjuncts'][cluster] = rules['disjuncts'][cluster]  # 81205 ad-hoc
            trace.append([cluster, rules['words'][i], rules['disjuncts'][i]])
            pruned_clusters.append(cluster)
            pruned_words.append(rules['words'][i])
            #TODO: remove entire row -- needs further disjuncts cleanup (errors in writefiles.py)
            #for key in rules.keys():
                #del rules[key][i]  #  value = rules['key'].pop(i)
            #FIXME: check disjunct indexing errors in writefiles.py lines 65,35 - ... 12-06_.ipynb
            #print('trace: cluster:', cluster, '-', (rules['words'][cluster]))
    #if len(trace) > 0:
        #print('removed cluster trace:', trace)
    #print('pruned_clusters:', pruned_clusters, 'pruned_words:', pruned_words)
    # TOD0?: remove disjuncts connected with deleted clusters...
    # TODO?: iterate: prune clusters ⇒ disjuncts ⇒ clusters ... ⇒ renumber & rename :(

    if verbose == 'debug':
        print('grammar_inducer.py line 170: rules.keys():\n',
              {key: len(rules[key]) for key in rules.keys()})

    return rules, {'learned_rules': len([x for i, x in enumerate(rules['parent'])
                                         if x == 0 and i > 0]),
                   'total_clusters': len(rules['cluster']) - 1}

# Notes:

# 80802 poc05.py restructured: induce_grammar ⇒ grammar_inducer.py v~80625
# 81102 max_disjuncts ⇒ induce_grammar
# 81204 add_disjuncts, check_cats, prune_cats :: resolve rules with empty dj list
# 81205
