-- 将“出路与毕业难度”拆成“毕业友好程度”和“出路去向”两个维度。
ALTER TABLE comments ADD COLUMN score_graduation REAL CHECK(score_graduation BETWEEN 0 AND 5);
