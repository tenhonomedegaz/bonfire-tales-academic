import openpyxl
import re

def normalize_name(name):
    if name is None:
        return ""
    return str(name).strip().lower()

def get_rows_with_header(filepath, name_col_name):
    wb = openpyxl.load_workbook(filepath, data_only=True)
    sheet = wb.active
    
    headers = [cell.value for cell in sheet[1]]
    
    name_idx = None
    for i, h in enumerate(headers):
        if h and str(h).strip().lower() == name_col_name.lower():
            name_idx = i
            break
            
    if name_idx is None:
        name_idx = 0
        
    items = {}
    for row in sheet.iter_rows(min_row=2, values_only=True):
        raw_name = row[name_idx]
        if raw_name:
            norm = normalize_name(raw_name)
            # transform row into dict
            row_dict = {headers[i]: row[i] for i in range(len(headers))}
            items[norm] = row_dict
            
    return items

def main():
    file1 = 'itemsbonfasporslot.xlsx'
    file2 = 'Loja de Itens - Bonfire Tales (1).xlsx'
    final_file = 'items_magicos_import_final.xlsx'
    
    items1 = get_rows_with_header(file1, 'nome')
    items2 = get_rows_with_header(file2, 'name')
    
    only_in_1 = set(items1.keys()) - set(items2.keys())
    only_in_2 = set(items2.keys()) - set(items1.keys())
    
    print(f"Unicos na planilha 1: {len(only_in_1)}")
    print(f"Unicos na planilha 2: {len(only_in_2)}")
    
    # Abrir planilha final
    wb_final = openpyxl.load_workbook(final_file)
    sheet_final = wb_final.active
    final_headers = [cell.value for cell in sheet_final[1]]
    
    # Criar um set de nomes ja existentes na planilha final para nao duplicar
    existing_names = set()
    name_col_idx_final = None
    for i, h in enumerate(final_headers):
        if h and str(h).strip().lower() == 'nome':
            name_col_idx_final = i
            break
            
    if name_col_idx_final is not None:
        for row in sheet_final.iter_rows(min_row=2, values_only=True):
            if row[name_col_idx_final]:
                existing_names.add(normalize_name(row[name_col_idx_final]))
                
    added_count = 0
    
    # Mapeamento e adicao da Planilha 1
    for norm_name in only_in_1:
        if norm_name in existing_names:
            continue
        row_data = items1[norm_name]
        
        new_row = []
        for header in final_headers:
            val = None
            if header == 'Nome': val = row_data.get('Nome')
            elif header == 'Slug': val = row_data.get('Slug')
            elif header == 'Tipo': val = row_data.get('Tipo')
            elif header == 'Slot': val = row_data.get('SlotCodigo')
            elif header == 'SlotNome': val = row_data.get('SlotNome')
            elif header == 'RequerSintonizacao': 
                att = row_data.get('Attunement')
                if att and str(att).strip().lower() in ['yes', 'sim', 'true', '1']:
                    val = True
                elif att and str(att).strip().lower() in ['no', 'nao', 'false', '0']:
                    val = False
                else:
                    val = att
            elif header == 'Preco': val = row_data.get('Value')
            elif header == 'Fonte': val = row_data.get('Source')
            elif header == 'IdOriginal': val = row_data.get('Id_Item')
            
            new_row.append(val)
            
        sheet_final.append(new_row)
        added_count += 1
        
    # Mapeamento e adicao da Planilha 2
    for norm_name in only_in_2:
        if norm_name in existing_names:
            continue
        row_data = items2[norm_name]
        
        new_row = []
        for header in final_headers:
            val = None
            if header == 'Nome': val = row_data.get('Name')
            elif header == 'Tipo': val = row_data.get('Tipo')
            elif header == 'Raridade': val = row_data.get('Rarity')
            elif header == 'Loja': val = row_data.get('Loja')
            # The header is 'Preço' in sheet 2, with special char
            elif header == 'Preco': 
                # Find the key that starts with Pre
                for k in row_data.keys():
                    if k and str(k).startswith('Pre'):
                        val = row_data[k]
                        break
                        
            new_row.append(val)
            
        sheet_final.append(new_row)
        added_count += 1
        
    wb_final.save(final_file)
    print(f"Finalizado! {added_count} novos itens foram adicionados à planilha {final_file}.")

if __name__ == '__main__':
    main()
