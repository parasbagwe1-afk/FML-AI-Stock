def item_lines_from_form(form):
    line_ids = form.getlist("line_id[]")
    item_ids = form.getlist("item_id[]")
    quantities = form.getlist("quantity[]")
    rates = form.getlist("rate[]")
    gst_percents = form.getlist("gst_percent[]")
    remarks = form.getlist("line_remarks[]")
    rows = []
    for index, item_id in enumerate(item_ids):
        rows.append(
            {
                "line_id": line_ids[index] if index < len(line_ids) else "",
                "item_id": item_id,
                "quantity": quantities[index] if index < len(quantities) else "",
                "rate": rates[index] if index < len(rates) else "",
                "gst_percent": gst_percents[index] if index < len(gst_percents) else "",
                "remarks": remarks[index] if index < len(remarks) else "",
            }
        )
    return rows


def transfer_lines_from_form(form):
    line_ids = form.getlist("line_id[]")
    item_ids = form.getlist("item_id[]")
    quantities = form.getlist("quantity[]")
    rows = []
    for index, item_id in enumerate(item_ids):
        rows.append(
            {
                "line_id": line_ids[index] if index < len(line_ids) else "",
                "item_id": item_id,
                "quantity": quantities[index] if index < len(quantities) else "",
            }
        )
    return rows
