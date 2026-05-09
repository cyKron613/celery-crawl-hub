CREATE TABLE IF NOT EXISTS sdc_test.ex_shipping_information
(
    uuid                CHAR(36) DEFAULT gen_random_uuid()::text NOT NULL,
    img_parse_url       TEXT,
    detail_url          TEXT,
    detail_title        TEXT,
    detail_date         DATE,
    detail_timestamptz  VARCHAR(30),
    detail_contents     TEXT,
    article_id          VARCHAR(50) NOT NULL,
    update_time         TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    class_level_1       VARCHAR(100),
    class_level_2       VARCHAR(100),
    news_source_name_cn VARCHAR(255),
    keyword1            VARCHAR(100),
    keyword2            VARCHAR(100),
    keyword3            VARCHAR(100),
    is_translated       VARCHAR(10) DEFAULT 'no' NOT NULL,
    abstract            TEXT,
    detail_title_cn     TEXT,
    detail_contents_cn  TEXT,
    abstract_cn         TEXT,
    obs_url             TEXT,
    PRIMARY KEY (article_id)
);

CREATE INDEX IF NOT EXISTS idx_article_id ON sdc_test.ex_shipping_information (article_id);

CREATE OR REPLACE FUNCTION update_ex_shipping_information_update_time()
RETURNS TRIGGER AS $$
BEGIN
    NEW.update_time = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ex_shipping_information_update_time ON sdc_test.ex_shipping_information;

CREATE TRIGGER trg_ex_shipping_information_update_time
BEFORE UPDATE ON sdc_test.ex_shipping_information
FOR EACH ROW
EXECUTE FUNCTION update_ex_shipping_information_update_time();