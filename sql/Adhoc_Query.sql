SELECT RecordType, ORDER_NO, OO_LIN, OO_PO FROM [dbo].[V_RAG_Vector] WHERE RecordType = 'OpenOrder' AND CUSTOMER = 'MINGO' ORDER BY chunk_id ASC

