from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `user_consents` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `agreement` VARCHAR(16) NOT NULL COMMENT 'TERMS: TERMS\nPRIVACY: PRIVACY\nSENSITIVE_HEALTH: SENSITIVE_HEALTH',
    `version` VARCHAR(20) NOT NULL,
    `is_agreed` BOOL NOT NULL,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `user_id` BIGINT NOT NULL,
    CONSTRAINT `fk_user_con_users_4a5cdd72` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
        ALTER TABLE `users` ADD `quiet_end` TIME(6);
        ALTER TABLE `users` ADD `nickname` VARCHAR(50) NOT NULL;
        ALTER TABLE `users` ADD `quiet_start` TIME(6);
        ALTER TABLE `users` DROP COLUMN `name`;
        ALTER TABLE `users` DROP COLUMN `phone_number`;
        ALTER TABLE `users` MODIFY COLUMN `email` VARCHAR(255) NOT NULL;
        ALTER TABLE `users` ADD UNIQUE INDEX `email` (`email`);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `users` DROP INDEX `email`;
        ALTER TABLE `users` ADD `name` VARCHAR(20) NOT NULL;
        ALTER TABLE `users` ADD `phone_number` VARCHAR(11) NOT NULL;
        ALTER TABLE `users` DROP COLUMN `quiet_end`;
        ALTER TABLE `users` DROP COLUMN `nickname`;
        ALTER TABLE `users` DROP COLUMN `quiet_start`;
        ALTER TABLE `users` MODIFY COLUMN `email` VARCHAR(40) NOT NULL;
        DROP TABLE IF EXISTS `user_consents`;"""


MODELS_STATE = (
    "eJztmm1z2jgQgP+Kh0+9mV4nOOHl+GaIc+EaoANO7q5NxyNsxWhiy8SSmzId/vtJso3fDW"
    "QgQC5fglnt2tpHa+1qya+a45rQJp8U6CFjVutIv2oYOJBdZEY+SjUwn8dyLqBgagtVEOtM"
    "CfWAQZn0AdgEMpEJieGhOUUuZlLs2zYXugZTRNiKRT5GTz7UqWtBOoMeG/j2nYkRNuFPSK"
    "Kv80f9AUHbTE0VmfzZQq7TxVzI+pheCUX+tKluuLbv4Fh5vqAzF6+0EaZcakEMPUAhvz31"
    "fD59PrvQz8ijYKaxSjDFhI0JH4Bv04S7GzIwXMz5sdkQ4aDFn/K7XL9oXbTPmxdtpiJmsp"
    "K0loF7se+BoSAw1GpLMQ4oCDQExpjbD+gRPqUcvN4MeMX0EiYZhGziWYQRsCqGkSCGGAfO"
    "jig64KduQ2xRHuByo1HB7E4Z966V8Qem9Rv3xmXBHMT4MBySgzEONgbJX40tIIbqpwmwfn"
    "a2AUCmVQpQjKUBsidSGLyDaYh/TUbDYogJkwzIW8wc/GYig36UbETo9+PEWkGRe80n7RDy"
    "ZCfhfRgo/2S59m5GXUHBJdTyxF3EDbqMMd8yHx4TLz8XTIHx+Aw8U8+NuLJbppsfcmQnKw"
    "EYWIIV95j7FyaRWyI29FxyEfLK1OIzDXJcmaWLrDeUXP6Q5fPzlnx23mw3LlqtRvtslWXy"
    "Q1Xpptv/k2ecVGyuT0HQAcjeZu9cGexm99w75f0nnxkgM2jqc0DIs+sVBGw5zALTE01Kcn"
    "uTpCS3y5MSH0uDxch4FNdbEE3anCbKxibpvVGe3Ru55M48NoN9Pk9Rxb4jSPbZlAA2YI5o"
    "bH1gnrWBcqN2JP73Hl+pwbfgs/YCzs0NMDdLKTezkKfIozMTLPKYLxmc4mBN2mTgsg0bUu"
    "TAT/ziOMO2gt+loqkZPk8+glRnMeYVVJka87QYUcasjBL/swGlMLkcByStPxCB6yzCIpML"
    "KkIu2DuTVSY30L4WgmYv7faYQ6N3yGshI6KzWhj9KMhNXde1IcAl9WnSLsN5ygz39aavqq"
    "pd8+2ORjepk1K3n6lBh7eDrspyvwDLlBBNlaZppqaDCtoha5FGZq9IdNtD0EGQ2oBQ3Xat"
    "IqiX4WtdTDVtWZWcTnVXmGjK4EuKM89afERObRiRNLdprG4i/d3XriX+Vfo6GqpFG4jQ47"
    "sIGwM+dXXsPrOwTbodiSNRuj/jQY5WBwXJs3oh05Y7WMhDFMjMB3OE7UUYRyeysmHIVy6s"
    "PzdfuLBpy/eFPejCislv0exLBACBns6xQM4kn/pC86vPY2gDWtz6T3TzesGdjnO5l1EMR9"
    "IkuX32PiMqJS3QBLTqTmhqod47om+yIwrYJgCdwh9DNmuYpG5w6J6Jpo4Hk44kPu7xl3H/"
    "Tun925HCi3s8UYeTvta/U/VrVbnRrjtSVvKS3kp9k+ZKvfwUVs+1V/6XP5Vu0gmUyzuBcq"
    "4TyM9KPDqL9pB1Z6yV3SsesvZ2ANjhGeu9NH8TFVxBac4T/rbpNmG0PuceyRK+WtrNFchp"
    "2HnSV64HkYU/w0Uu5ZaXwMdJuaz2ZWIPPK8KvWQAMfeYUzDYeHrKpKdcqrXla/4HwfI/t+"
    "9WhQ=="
)
