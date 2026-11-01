/* ==========================================================================
   SoftOne SQL script για το service "SqlData"
   Όνομα script στο SoftOne:  AIC_SALES_STATS
   Παράμετροι:  :1 = Από ημερομηνία (YYYYMMDD)   :2 = Έως ημερομηνία (YYYYMMDD)

   Επιστρέφει γραμμές πωλήσεων (1 γραμμή = 1 είδος παραστατικού).
   ΣΗΜΑΝΤΙΚΟ: Επιβεβαιώστε με τον SoftOne partner σας:
     - ποιες σειρές/τύπους παραστατικών μετράτε ως πωλήσεις
     - το πρόσημο των πιστωτικών (εδώ μέσω TPRMS.FLG01 – προσαρμόστε)
     - το πεδίο κόστους (εδώ MTRL.PURLPRICE ως προσέγγιση)
   ========================================================================== */
SELECT
    F.FINDOC                                   AS DOC_ID,
    CONVERT(varchar(10), F.TRNDATE, 23)        AS TRNDATE,
    F.FINCODE                                  AS DOC_NO,
    S.NAME                                     AS SERIES,
    B.NAME                                     AS BRANCH,
    T.CODE                                     AS CUSTOMER_CODE,
    T.NAME                                     AS CUSTOMER,
    ISNULL(T.CITY, '')                         AS CITY,
    ISNULL(P.NAME, '-')                        AS SALESMAN,
    M.CODE                                     AS ITEM_CODE,
    M.NAME                                     AS ITEM,
    ISNULL(G.NAME, '-')                        AS ITEM_GROUP,
    ISNULL(MN.NAME, '-')                       AS BRAND,
    L.QTY1 * SG.SIGN                           AS QTY,
    L.LINEVAL * SG.SIGN                        AS NET_VALUE,
    L.QTY1 * ISNULL(M.PURLPRICE, 0) * SG.SIGN  AS COST
FROM FINDOC F
JOIN MTRLINES L     ON L.FINDOC = F.FINDOC
JOIN MTRL M         ON M.MTRL = L.MTRL
JOIN TRDR T         ON T.TRDR = F.TRDR
JOIN SERIES S       ON S.COMPANY = F.COMPANY AND S.SOSOURCE = F.SOSOURCE AND S.SERIES = F.SERIES
LEFT JOIN BRANCH B  ON B.COMPANY = F.COMPANY AND B.BRANCH = F.BRANCH
LEFT JOIN PRSN P    ON P.PRSN = F.SALESMAN
LEFT JOIN MTRGROUP G ON G.COMPANY = M.COMPANY AND G.MTRGROUP = M.MTRGROUP AND G.SODTYPE = M.SODTYPE
LEFT JOIN MTRMANFCTR MN ON MN.COMPANY = M.COMPANY AND MN.MTRMANFCTR = M.MTRMANFCTR
LEFT JOIN TPRMS TP  ON TP.COMPANY = F.COMPANY AND TP.SODTYPE = F.SODTYPE AND TP.TPRMS = F.TPRMS
CROSS APPLY (SELECT CASE WHEN ISNULL(TP.FLG01, 1) < 0 THEN -1 ELSE 1 END AS SIGN) SG
WHERE F.COMPANY  = :X.SYS.COMPANY
  AND F.SOSOURCE = 1351            -- Πωλήσεις
  AND F.SODTYPE  = 13              -- Πελάτες
  AND F.ISCANCEL = 0
  AND F.FULLYTRANSF IN (0, 2)      -- αποκλεισμός μετασχηματισμένων (π.χ. ΔΑ που έγιναν τιμολόγια)
  AND F.TRNDATE >= :1
  AND F.TRNDATE <  DATEADD(day, 1, :2)
ORDER BY F.TRNDATE
