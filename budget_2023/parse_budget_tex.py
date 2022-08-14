#!/usr/bin/env python3
import sys
import re
import itertools

def parse_budget(filename):
    text = open(filename, 'rt').read()
    tables = extract_tables(text)
    parameter_values_dict, parameter_values = get_specifiers(tables['parameters'])
    costs = get_costs(tables['costs'], parameter_values)
    totals = compute_totals(costs, parameter_values)
    # show_parsed_tables(tables)
    show_cost_list(costs)
    show_totals(totals)
    save_totals(totals)

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
    tokens = [
        re.sub(r'\\costlabel{.+}', '', token)
        for token in tokens
    ]
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
    costs = [
        {
            'or-tags' : get_tags(row[2], parameter_values, 'or'),
            'and-tags' : get_tags(row[2], parameter_values, 'and'),
            'amount' : get_dollars(row[3]),
        }
        for row in costs_table['rows']
    ]
    return [
        {
            'singleton-tag' : cost['or-tags'] if len(cost['or-tags']) == 1 else [],
            'or-tags' : cost['or-tags'],
            'and-tags' : cost['and-tags'],
            'amount' : cost['amount'],
        }
        for cost in costs
    ]

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

def compute_totals(costs, parameter_values):
    cases = list(itertools.product(*parameter_values))
    return list(zip(cases, [compute_total_in_case(case, costs, parameter_values) for case in cases]))

def compute_total_in_case(case, costs, parameter_values):
    total_cost = 0
    for cost in costs:
        if check_cost_applies_in_case(cost, case, parameter_values):
            total_cost = total_cost + cost['amount']
    return total_cost

def check_cost_applies_in_case(cost, case, parameter_values):
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
\begin{tabular}{lllr}
\multicolumn{3}{c}{Scenario} & Total cost \\ \hline
'''
    footer = r'''
\end{tabular}
\end{center}
'''
    with open('totals_by_scenario.tex', 'wt') as file:
        rows = '\n'.join([
            ' & '.join(row[0]) + ' & ' + str(row[1]) + r' \\'
            for row in totals
        ])
        tex_fragment = header + rows + footer
        file.write(tex_fragment)

    with open('totals_by_scenario_sorted.tex', 'wt') as file:
        rows = '\n'.join([
            ' & '.join(row[0]) + ' & ' + str(row[1]) + r' \\'
            for row in sorted(totals, key=lambda row: -1 * row[1])
        ])
        tex_fragment = header + rows + footer
        file.write(tex_fragment)

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
