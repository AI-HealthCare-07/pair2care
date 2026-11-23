from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `health_profiles` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `kind` VARCHAR(10) NOT NULL COMMENT 'ONBOARDING: ONBOARDING\nWEEKLY: WEEKLY',
    `survey_version` VARCHAR(20) NOT NULL,
    `height_cm` DECIMAL(4,1) NOT NULL,
    `weight_kg` DECIMAL(4,1) NOT NULL,
    `waist_cm` DECIMAL(4,1),
    `father_diabetes_history` SMALLINT NOT NULL,
    `mother_diabetes_history` SMALLINT NOT NULL,
    `sibling_diabetes_history` SMALLINT NOT NULL,
    `father_hypertension_history` SMALLINT NOT NULL,
    `mother_hypertension_history` SMALLINT NOT NULL,
    `sibling_hypertension_history` SMALLINT NOT NULL,
    `alcohol_ever` SMALLINT NOT NULL,
    `alcohol_frequency` SMALLINT NOT NULL,
    `alcohol_amount` SMALLINT NOT NULL,
    `binge_frequency` SMALLINT NOT NULL,
    `smoking_lifetime` SMALLINT NOT NULL,
    `smoking_current` SMALLINT NOT NULL,
    `cigarettes_per_day` SMALLINT NOT NULL,
    `heated_tobacco` SMALLINT NOT NULL,
    `liquid_ecig` SMALLINT NOT NULL,
    `is_hypertension_diagnosed` BOOL NOT NULL,
    `is_diabetes_diagnosed` BOOL NOT NULL,
    `is_pregnant` BOOL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `user_id` BIGINT NOT NULL,
    CONSTRAINT `fk_health_p_users_35ba10a2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    KEY `idx_health_prof_user_id_fff998` (`user_id`, `created_at`)
) CHARACTER SET utf8mb4 COMMENT='설문 한 번 = 한 행 (재설문도 새 행으로 쌓음, 수정 없음).';
        CREATE TABLE IF NOT EXISTS `checkup_records` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `checked_on` DATE NOT NULL,
    `systolic_bp` SMALLINT,
    `diastolic_bp` SMALLINT,
    `fasting_glucose` SMALLINT,
    `waist_cm` DECIMAL(4,1),
    `triglyceride` SMALLINT,
    `hdl_cholesterol` SMALLINT,
    `hba1c` DECIMAL(3,1),
    `source` VARCHAR(6) NOT NULL COMMENT 'MANUAL: MANUAL\nOCR: OCR' DEFAULT 'MANUAL',
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `user_id` BIGINT NOT NULL,
    CONSTRAINT `fk_checkup__users_595af235` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    KEY `idx_checkup_rec_user_id_967976` (`user_id`, `checked_on`)
) CHARACTER SET utf8mb4 COMMENT='건강검진 결과지 한 장 = 한 행.';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS `health_profiles`;
        DROP TABLE IF EXISTS `checkup_records`;"""


MODELS_STATE = (
    "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"
    "F6cV"
)
