/* 1. DROP EXISTING VIEW 
   Ensures a clean slate before creating the new definition.
*/
IF OBJECT_ID('dbo.V_RAG_Vector', 'V') IS NOT NULL
    DROP VIEW dbo.V_RAG_Vector;
GO

/* 2. CREATE NEW UNIFIED VIEW 
   Combines History, Open Orders, and Shipment Lines into a single source.
   Includes 'Index_WaterMark' for Incremental Indexing.
*/
CREATE VIEW V_RAG_Vector AS

/* ==================================================================================
   PART 1: HISTORICAL SHIPMENTS (V_ORDER_HIST_LINE + V_CUSTOMER_MASTER)
   ================================================================================== */
SELECT 
    -- 1. UNIQUE SEARCH ID (Type + Order + Line + Suffix)
    CONCAT('HIST-', TRIM(H.ORDER_NO), '-', TRIM(H.ORDER_LINE)) AS chunk_id,
    
    -- 2. HIGH WATER MARK (For Incremental Updates)
    -- Logic: Use Invoice Date (completion); if null, use Ship Date. Cast to DATETIME2 to match other tables.
    CAST(ISNULL(H.DATE_INVOICE, H.DATE_SHIPPED) AS DATETIME2(0)) AS Index_WaterMark,

    'History' AS RecordType,

    -- 3. VECTOR DATA CHUNK (Natural Language Summary with Rich Customer Info)
    CONCAT(
        'Record Type: Historical Order. ',
        'Customer Name: ', TRIM(C.NAME_CUSTOMER), '. ',
        'Customer Code: ', TRIM(H.CUSTOMER), '. ',
        'Address: ', TRIM(C.ADDRESS1), ' ', TRIM(C.ADDRESS2), ', ', TRIM(C.CITY), ', ', TRIM(C.STATE), ' ', TRIM(C.ZIP), '. ',
        'Phone: ', TRIM(C.TELEPHONE), '. ',
        'Order #: ', TRIM(H.ORDER_NO), '-', TRIM(H.ORDER_LINE), '. ',
        'Invoice: ', TRIM(H.INVOICE), '. ',
        'Shipped Date: ', FORMAT(H.DATE_SHIPPED, 'yyyy-MM-dd'), '. ',
        'Part Number: ', TRIM(H.PART), '. ',
        'Part Description: ', TRIM(H.DESCRIPTION), '. ',
        'Quantity Shipped: ', CAST(H.QTY_SHIPPED AS NVARCHAR(20)), ' ', TRIM(H.UM), '. ',
        'Price: $', CAST(H.PRICE AS NVARCHAR(20)), '. ',
        'Total: $', CAST(H.EXTENSION AS NVARCHAR(20)), '.'
    ) AS VectorData,

    -- 4. CUSTOMER MASTER COLUMNS (Common to all)
    C.NAME_CUSTOMER, C.ADDRESS1, C.ADDRESS2, C.CITY, C.STATE, C.ZIP, C.COUNTRY, C.COUNTY, C.CREDIT, C.TELEPHONE,

    -- 5. HISTORY SPECIFIC COLUMNS (Present)
    H.INVOICE, H.ORDER_NO, H.ORDER_SUFFIX, H.ORDER_LINE, H.CUSTOMER, H.CUSTOMER_PO, 
    H.DATE_ORDER, H.DATE_ORDER_DUE, H.DATE_SHIPPED, H.DATE_INVOICE, H.SALESPERSON, H.SHIP_VIA, 
    H.PART, H.DESCRIPTION, H.CUSTOMER_PART, H.QTY_ORDERED, H.QTY_SHIPPED, H.QTY_BO, H.QTY_ORIGINAL, 
    H.UM, H.JOB, H.DATE_DUE, H.GL_ACCOUNT, H.PRODUCT_LINE, H.PRICE, H.EXTENSION,

    -- 6. COLUMNS FROM OTHER TABLES (Set to NULL)
    -- From TEMP_OO (Open Orders)
    NULL AS PROM_DT, NULL AS OO_LIN, NULL AS OO_PO, NULL AS OO_DESC, NULL AS MTRL, NULL AS LDWTG, 
    NULL AS SPECIFICATION, NULL AS RECORD_NO, NULL AS SFX, NULL AS SHIP_ID, NULL AS CMPLT_200, NULL AS SCRP_200, NULL AS LAST_UPD,
    -- From V_SHIPMENT_LINES (Shipment Lines)
    NULL AS SL_ORDER_REC, NULL AS SL_DATE_SHIP, NULL AS SL_DATE_ITEM_PROMISE

FROM dbo.V_ORDER_HIST_LINE H
LEFT JOIN dbo.V_CUSTOMER_MASTER C ON H.CUSTOMER = C.CUSTOMER

UNION ALL

/* ==================================================================================
   PART 2: OPEN ORDERS (TEMP_OO + V_CUSTOMER_MASTER)
   ================================================================================== */
SELECT 
    -- 1. UNIQUE SEARCH ID
    CONCAT('OPEN-', TRIM(O.[ORDER]), '-', TRIM(O.LIN)) AS chunk_id,
    
    -- 2. HIGH WATER MARK (For Incremental Updates)
    -- Logic: Use Last Updated timestamp; if null, use Date Ordered.
    ISNULL(O.LAST_UPD, O.DATE_ORDER) AS Index_WaterMark,

    'OpenOrder' AS RecordType,

    -- 3. VECTOR DATA CHUNK (Natural Language Summary with Rich Customer Info)
    CONCAT(
        'Record Type: Open Order. ',
        'Customer Name: ', TRIM(C.NAME_CUSTOMER), '. ',
        'Customer Code: ', TRIM(O.CUSTOMER), '. ',
        'Address: ', TRIM(C.ADDRESS1), ' ', TRIM(C.ADDRESS2), ', ', TRIM(C.CITY), ', ', TRIM(C.STATE), ' ', TRIM(C.ZIP), '. ',
        'Phone: ', TRIM(C.TELEPHONE), '. ',
        'Order #: ', TRIM(O.[ORDER]), '-', TRIM(O.LIN), '. ',
        'PO: ', TRIM(O.PO), '. ',
        'Status: Backordered / Open. ',
        'Promised Date: ', FORMAT(O.PROM_DT, 'yyyy-MM-dd'), '. ',
        'Part Number: ', TRIM(O.PART), '. ',
        'Part Description: ', TRIM(O.[DESC]), '. ',
        'Quantity Ordered: ', CAST(O.[QTY BO] AS NVARCHAR(20)), ' ', TRIM(O.UM), '. ',
        'Price: $', CAST(O.PRICE AS NVARCHAR(20)), '.'
    ) AS VectorData,

    -- 4. CUSTOMER MASTER COLUMNS
    C.NAME_CUSTOMER, C.ADDRESS1, C.ADDRESS2, C.CITY, C.STATE, C.ZIP, C.COUNTRY, C.COUNTY, C.CREDIT, C.TELEPHONE,

    -- 5. HISTORY SPECIFIC COLUMNS (NULL)
    NULL AS INVOICE, 
    O.[ORDER] AS ORDER_NO, -- Map to Common Order No
    O.SFX AS ORDER_SUFFIX, -- Map to Common Suffix
    NULL AS ORDER_LINE, 
    O.CUSTOMER, 
    NULL AS CUSTOMER_PO, 
    CAST(O.DATE_ORDER AS DATE) AS DATE_ORDER, -- Cast DateTime2 to Date matches Hist
    NULL AS DATE_ORDER_DUE, NULL AS DATE_SHIPPED, NULL AS DATE_INVOICE, NULL AS SALESPERSON, NULL AS SHIP_VIA, 
    O.PART, 
    O.[DESC] AS DESCRIPTION,
    NULL AS CUSTOMER_PART, NULL AS QTY_ORDERED, NULL AS QTY_SHIPPED, 
    O.[QTY BO] AS QTY_BO, -- Map Common Qty
    O.[ORIG QTY] AS QTY_ORIGINAL, -- Map Common Qty
    O.UM, 
    O.JOB, 
    NULL AS DATE_DUE, 
    NULL AS GL_ACCOUNT, 
    O.PRODUCT_LINE, 
    CAST(O.PRICE AS DECIMAL(16,6)) AS PRICE, -- Cast to match Hist precision
    NULL AS EXTENSION,

    -- 6. COLUMNS FROM TEMP_OO (Present)
    O.PROM_DT, O.LIN AS OO_LIN, O.PO AS OO_PO, O.[DESC] AS OO_DESC, O.MTRL, O.LDWTG, 
    O.Specification, O.RECORD_NO, O.SFX, O.SHIP_ID, O.CMPLT_200, O.SCRP_200, O.LAST_UPD,
    -- From V_SHIPMENT_LINES (NULL)
    NULL AS SL_ORDER_REC, NULL AS SL_DATE_SHIP, NULL AS SL_DATE_ITEM_PROMISE

FROM dbo.TEMP_OO O
LEFT JOIN dbo.V_CUSTOMER_MASTER C ON O.CUSTOMER = C.CUSTOMER

UNION ALL

/* ==================================================================================
   PART 3: SHIPMENT LINES (V_SHIPMENT_LINES + V_CUSTOMER_MASTER)
   ================================================================================== */
SELECT 
    -- 1. UNIQUE SEARCH ID
    CONCAT('SHIP-', TRIM(S.ORDER_NO), '-', TRIM(S.ORDER_REC)) AS chunk_id,
    
    -- 2. HIGH WATER MARK (For Incremental Updates)
    -- Logic: Use Date Shipped (already DATETIME2(0))
    S.DATE_SHIP AS Index_WaterMark,

    'ShipmentLine' AS RecordType,

    -- 3. VECTOR DATA CHUNK (Natural Language Summary with Rich Customer Info)
    CONCAT(
        'Record Type: Shipment. ',
        'Customer Name: ', TRIM(C.NAME_CUSTOMER), '. ',
        'Customer Code: ', TRIM(S.CUSTOMER), '. ',
        'Address: ', TRIM(C.ADDRESS1), ' ', TRIM(C.ADDRESS2), ', ', TRIM(C.CITY), ', ', TRIM(C.STATE), ' ', TRIM(C.ZIP), '. ',
        'Phone: ', TRIM(C.TELEPHONE), '. ',
        'Order #: ', TRIM(S.ORDER_NO), '. ',
        'Invoice: ', TRIM(S.INVOICE), '. ',
        'Shipped Date: ', FORMAT(S.DATE_SHIP, 'yyyy-MM-dd'), '. ',
        'Part Number: ', TRIM(S.PART), '. ',
        'Part Description: ', TRIM(S.ORDER_DESC), '. ',
        'Quantity Shipped: ', CAST(S.QTY_SHIPPED AS NVARCHAR(20)), ' ', TRIM(S.UM_ORDER), '. ',
        'Price: $', CAST(S.PRICE AS NVARCHAR(20)), '. ',
        'Total: $', CAST(S.EXTENSION AS NVARCHAR(20)), '.'
    ) AS VectorData,

    -- 4. CUSTOMER MASTER COLUMNS
    C.NAME_CUSTOMER, C.ADDRESS1, C.ADDRESS2, C.CITY, C.STATE, C.ZIP, C.COUNTRY, C.COUNTY, C.CREDIT, C.TELEPHONE,

    -- 5. HISTORY SPECIFIC COLUMNS (Mixed Present/NULL)
    S.INVOICE, S.ORDER_NO, S.ORDER_SUFFIX, NULL AS ORDER_LINE, S.CUSTOMER, NULL AS CUSTOMER_PO, 
    CAST(S.DATE_ORDER AS DATE) AS DATE_ORDER, -- Cast DateTime2 to Date
    NULL AS DATE_ORDER_DUE, 
    CAST(S.DATE_SHIP AS DATE) AS DATE_SHIPPED, -- Cast DateTime2 to Date
    NULL AS DATE_INVOICE, NULL AS SALESPERSON, NULL AS SHIP_VIA, 
    S.PART, S.ORDER_DESC AS DESCRIPTION, NULL AS CUSTOMER_PART, 
    S.QTY_ORDERED, S.QTY_SHIPPED, S.QTY_BO, S.QTY_ORIGINAL, 
    S.UM_ORDER AS UM, -- Map UM
    NULL AS JOB, NULL AS DATE_DUE, 
    S.GL_ACCOUNT, 
    NULL AS PRODUCT_LINE, NULL AS PRICE, 
    S.EXTENSION,

    -- 6. COLUMNS FROM TEMP_OO (NULL)
    NULL AS PROM_DT, NULL AS OO_LIN, NULL AS OO_PO, NULL AS OO_DESC, NULL AS MTRL, NULL AS LDWTG, 
    NULL AS SPECIFICATION, NULL AS RECORD_NO, NULL AS SFX, NULL AS SHIP_ID, NULL AS CMPLT_200, NULL AS SCRP_200, NULL AS LAST_UPD,
    
    -- 7. COLUMNS FROM V_SHIPMENT_LINES (Present)
    S.ORDER_REC AS SL_ORDER_REC, S.DATE_SHIP AS SL_DATE_SHIP, S.DATE_ITEM_PROMISE AS SL_DATE_ITEM_PROMISE

FROM dbo.V_SHIPMENT_LINES S
LEFT JOIN dbo.V_CUSTOMER_MASTER C ON S.CUSTOMER = C.CUSTOMER;
GO