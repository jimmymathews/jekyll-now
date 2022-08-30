#!/usr/bin/env python3
import sys
import re
import itertools

def parse_budget(filename):
    text = open(filename, 'rt').read()
    tables = extract_tables(text)
    parameter_values_dict, parameter_values = get_specifiers(tables['parameters'])
    costs = get_costs(tables['costs'], parameter_values)
    cuts = get_cuts(tables['costs'])
    priority_values = sorted(list(set([cost['priority'] for cost in costs])))

    totals = compute_totals(costs, parameter_values, priority_values, cuts)
    save_totals(totals)

    scenarios = compute_all_scenarios(costs, parameter_values, priority_values, cuts)
    save_all_scenarios(scenarios)

def extract_tables(text):
    table_sections_pattern = re.compile(r'\\begin{tabular}(.+?)\\end{tabular}', flags=re.DOTALL)
    sections = table_sections_pattern.findall(text)
    inner_sections = [
        re.sub(table_sections_pattern, '\1', s)
        for s in sections
    ]
    inner_sections = [
        re.sub(r'^{.*?}', '', s)
        for s in inner_sections
    ]
    line_pattern = re.compile(r'^(.+?)(\s*)\\\\', flags=re.MULTILINE)
    table_lines = [
        [matches[0] for matches in line_pattern.findall(s)]
        for s in inner_sections
    ]
    table_tokens = [
        [
            aggressive_split(line)
            for line in table
        ]
        for table in table_lines
    ]

    return {
        'parameters' : separate_header(table_tokens[0]),
        'costs' : separate_header(table_tokens[1]),
    }

def aggressive_split(line):
    tokens = line.split('&')
    stripped_tokens = [
        token.rstrip().lstrip()
        for token in tokens
    ]
    return stripped_tokens

def separate_header(table_rows):
    return {
        'header' : table_rows[0],
        'rows' : table_rows[1:],
    }

def get_specifiers(parameters):
    parameter_name = ''
    parameter_values = {}
    parameter_names = []
    for row in parameters['rows']:
        if row[0] != '':
            parameter_name = row[0]
            parameter_names.append(parameter_name)
            parameter_values[parameter_name] = []
        parameter_values[parameter_name].append(row[2])

    return parameter_values, [parameter_values[name] for name in parameter_names]

def get_costs(costs_table, parameter_values):
    category_name = costs_table['rows'][0][0]
    costs = []
    for row in costs_table['rows']:
        if re.search(r'%', row[3]):
            continue
        specific_name = ''
        if re.search(r'^\$\\quad\$', row[0]):
            specific_name = re.sub(r'\$\\quad\$', '', row[0])
        if specific_name == '':
            if row[0] != '':
                category_name = row[0]
        if specific_name != '':
            name = '%s (%s)' % (category_name, specific_name)
        else:
            name = category_name
        if row[3] == '':
            continue
        cost = {
            'or-tags' : get_tags(row[2], parameter_values, 'or'),
            'and-tags' : get_tags(row[2], parameter_values, 'and'),
            'amount' : get_dollars(row[3]),
            'name' : name,
            'link reference' : re.sub('costlabel', 'ref', row[1]),
            'category name' : category_name,
            'specific name' : specific_name,
            'priority' : int(row[4]),
        }
        costs.append(cost)

    return [
        {
            'singleton-tag' : cost['or-tags'] if len(cost['or-tags']) == 1 else [],
            'or-tags' : cost['or-tags'],
            'and-tags' : cost['and-tags'],
            'amount' : cost['amount'],
            'priority' : cost['priority'],
            'name' : cost['name'],
            'link reference' : cost['link reference'],
        }
        for cost in costs
    ]

def get_cuts(costs_table):
    cuts = []
    for row in costs_table['rows']:
        if re.search(r'%', row[3]):
            cuts.append({
                'name' : row[0],
                'link reference' : re.sub('costlabel', 'ref', row[1]),
                'percentage' : float(re.sub('%', '', re.sub(r'\\', '', row[3]))),
            })
    return cuts

def get_tags(specifier_text, parameter_values, delimiter):
    all_values = itertools.chain(*parameter_values)
    tokens = specifier_text.split(delimiter)
    if len(tokens) > 1:
        tokens = [token.rstrip().lstrip() for token in tokens]
        return sorted(list(set(all_values).intersection(tokens)))
    else:
        if tokens[0] in all_values:
            return tokens
    return []

def get_dollars(text):
    return float(re.search(r'\$?(\d+\.?\d*)', text).group(1))

def compute_totals(costs, parameter_values, priority_values, cuts):
    extended_cases = get_extended_cases(parameter_values, priority_values)
    return list(zip(extended_cases, [compute_total_in_case(extended_case, costs, parameter_values, cuts) for extended_case in extended_cases]))

def get_extended_cases(parameter_values, priority_values):
    extended_parameter_values = parameter_values + [priority_values]
    return list(itertools.product(*extended_parameter_values))

def compute_total_in_case(extended_case, costs, parameter_values, cuts):
    total_cost = 0
    for cost in costs:
        if check_cost_applies_in_case(cost, extended_case, parameter_values):
            total_cost = total_cost + cost['amount']

    if not cuts is None:
        initial_amount = total_cost
        adjustments = get_adjustments_for_cuts(extended_case, costs, parameter_values, cuts, initial_amount)
        total_cost = total_cost + sum([a[2] for a in adjustments])

    return int(total_cost)

def get_adjustments_for_cuts(extended_case, costs, parameter_values, cuts, initial_amount):
    rows = []
    for cut in cuts:
        fraction = (1/100) * cut['percentage']
        cut_amount = (fraction/(1 - fraction)) * initial_amount 
        rows.append([
            cut['name'],
            cut['link reference'],
            int(cut_amount),
        ])
    return rows

def check_cost_applies_in_case(cost, extended_case, parameter_values):
    if cost['priority'] > get_priority(extended_case):
        return False

    case = get_case(extended_case)
    if applies_to_all(cost):
        return True

    if len(cost['singleton-tag']) == 1 and cost['singleton-tag'][0] in case:
        return True

    or_conditions = cost['or-tags']
    if len(or_conditions) > 1:
        if any([condition in case for condition in or_conditions]):
            return True

    and_conditions = cost['and-tags']
    if len(and_conditions) > 1:
        if all([condition in case for condition in and_conditions]):
            return True

def applies_to_all(cost):
    return (cost['singleton-tag'] == [] and cost['or-tags'] == [] and cost['and-tags'] == [])

def save_totals(totals):
    header = r'''
\begin{center}
\begin{longtable}{llllr}
\multicolumn{4}{c}{Scenario} & Total cost \\ \hline
'''
    footer = r'''
\end{longtable}
\end{center}
'''
    with open('totals_by_scenario.tex', 'wt') as file:
        rows = '\n'.join([
            ' & '.join([str(x) for x in row[0]]) + ' & ' + str(row[1]) + r' \\'
            for row in totals
        ])
        tex_fragment = header + rows + footer
        file.write(tex_fragment)

    with open('totals_by_scenario_sorted.tex', 'wt') as file:
        rows = '\n'.join([
            ' & '.join([str(x) for x in row[0]]) + ' & ' + str(row[1]) + r' \\'
            for row in sorted(totals, key=lambda row: -1 * row[1])
        ])
        tex_fragment = header + rows + footer
        file.write(tex_fragment)

def compute_all_scenarios(costs, parameter_values, priority_values, cuts):
    extended_cases = get_extended_cases(parameter_values, priority_values)
    return [
        {
            'description' : r'\section*{%s (include items of priority rank $\leq$ %s)}' % (' '.join([str(entry) for entry in get_case(extended_case)]), str(get_priority(extended_case))),
            'rows' : [extract_simplified_cost_item(cost) for cost in cost_list] + get_adjustments_for_cuts(extended_case, costs, parameter_values, cuts, compute_total_in_case(extended_case, cost_list, parameter_values, cuts=None)),
            'total' : compute_total_in_case(extended_case, cost_list, parameter_values, cuts),
        }
        for extended_case, cost_list in list(zip(extended_cases, [compute_cost_list_in_case(extended_case, costs, parameter_values) for extended_case in extended_cases]))
    ]

def get_case(extended_case):
    return extended_case[0:-1]

def get_priority(extended_case):
    return extended_case[-1]

def extract_simplified_cost_item(cost):
    return [cost['name'], cost['link reference'], str(int(cost['amount']))]

def compute_cost_list_in_case(extended_case, costs, parameter_values):
    return [
        cost
        for cost in costs
        if check_cost_applies_in_case(cost, extended_case, parameter_values)
    ]

def save_all_scenarios(scenarios):
    separator = r'''\newpage
'''
    tex_fragment = separator.join([
        create_scenario_page(scenario)
        for scenario in scenarios
    ])
    with open('all_scenarios.tex', 'wt') as file:
        file.write(tex_fragment)

def create_scenario_page(scenario):
    header = r'''
\begin{center}
\begin{tabular}{llr}
Item & Reference & Cost (USD) \\ \hline
'''
    footer = r'''
\end{tabular}
\end{center}
'''
    rows = '\n'.join([
        ' & '.join([str(entry) for entry in row]) + r' \\'
        for row in scenario['rows']
    ])
    rows = rows + r' \hline' + '\n' + 'total &  & %s' % str(scenario['total'])
    return scenario['description'] + header + rows + footer

def show_parsed_tables(tables):
    for key, table in tables.items():
        print(key)
        print('header: %s' % table['header'])
        print('rows:')
        for row in table['rows']:
            print(row)
        print('')

def show_cost_list(costs):
    print('Costs and their domains of applicability:')
    print('')
    for row in costs:
        print('amount: %s' % row['amount'])
        print('or conditions: %s' % row['or-tags'])
        print('and conditions: %s' % row['and-tags'])
        print('single tag: %s' % row['singleton-tag'])
        print('')
    print('')

def show_totals(totals):
    print('Totals by case:')
    print('')
    for row in totals:
        print('%s      %s' % (row[1], row[0]))
    print('')

if __name__=='__main__':
    parse_budget(sys.argv[1])
