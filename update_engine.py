
with open("chat_engine.py", "r", encoding="utf-8") as f:
    content = f.read()

dispatch_code = """
        elif fn_name == "create_clinic":
            result = await api_client.create_clinic(args)
        elif fn_name == "update_clinic":
            result = await api_client.update_clinic(args["clinic_id"], args.get("data", {}))
        elif fn_name == "delete_clinic":
            result = await api_client.delete_clinic(args["clinic_id"])
        elif fn_name == "create_consultation":
            result = await api_client.create_consultation(args)
        elif fn_name == "update_consultation":
            cid = args.pop("consultation_id")
            result = await api_client.update_consultation(cid, args)
        elif fn_name == "complete_consultation":
            result = await api_client.complete_consultation(args["consultation_id"])
        elif fn_name == "cancel_consultation":
            result = await api_client.cancel_consultation(args["consultation_id"])
        elif fn_name == "update_user":
            result = await api_client.update_user(args["user_id"], args.get("data", {}))
"""

if 'elif fn_name == "create_clinic":' not in content:
    content = content.replace(
        'elif fn_name == "get_all_users":\n            result = await api_client.get_all_users()',
        f'elif fn_name == "get_all_users":\n            result = await api_client.get_all_users(){dispatch_code}'
    )

with open("chat_engine.py", "w", encoding="utf-8") as f:
    f.write(content)
