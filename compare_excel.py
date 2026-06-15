import openpyxl

def get_items(filepath):
    wb = openpyxl.load_workbook(filepath, data_only=True)
    sheet = wb.active
    
    # Procurar a coluna de nome. Normalmente é "Nome", "Item", "Name"
    headers = [cell.value for cell in sheet[1]]
    
    name_idx = None
    for i, h in enumerate(headers):
        if h and str(h).strip().lower() in ['nome', 'item', 'name', 'nome do item']:
            name_idx = i
            break
            
    if name_idx is None:
        # Tenta usar a primeira coluna se nao achar o nome
        name_idx = 0
        
    items = set()
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if row[name_idx]:
            # Normalizar para evitar problemas de case/espacos
            items.add(str(row[name_idx]).strip().lower())
            
    return items, headers[name_idx]

def main():
    file1 = 'itemsbonfasporslot.xlsx'
    file2 = 'Loja de Itens - Bonfire Tales (1).xlsx'
    
    items1, col1 = get_items(file1)
    items2, col2 = get_items(file2)
    
    only_in_1 = items1 - items2
    only_in_2 = items2 - items1
    
    with open('relatorio_diferencas_itens.txt', 'w', encoding='utf-8') as f:
        f.write(f"Relatório de Diferenças entre as Planilhas de Itens\n")
        f.write(f"===================================================\n\n")
        
        f.write(f"Planilha 1: {file1} (Usando coluna: {col1})\n")
        f.write(f"Planilha 2: {file2} (Usando coluna: {col2})\n\n")
        
        f.write(f"--- Itens presentes APENAS na Planilha 1 ({file1}) ---\n")
        if only_in_1:
            for item in sorted(list(only_in_1)):
                f.write(f"- {item.title()}\n")
        else:
            f.write("Nenhum. Todos os itens desta planilha estao na outra.\n")
            
        f.write(f"\n--- Itens presentes APENAS na Planilha 2 ({file2}) ---\n")
        if only_in_2:
            for item in sorted(list(only_in_2)):
                f.write(f"- {item.title()}\n")
        else:
            f.write("Nenhum. Todos os itens desta planilha estao na outra.\n")

    print("Relatório salvo em relatorio_diferencas_itens.txt")

if __name__ == '__main__':
    main()
