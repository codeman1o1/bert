/// <reference path="../pb_data/types.d.ts" />
migrate((db) => {
  const collection = new Collection({
    "id": "yq5t5fajqdx343u",
    "created": "2024-06-27 17:25:18.387Z",
    "updated": "2024-06-27 17:25:18.387Z",
    "name": "vcmaker",
    "type": "base",
    "system": false,
    "schema": [
      {
        "system": false,
        "id": "x2mf2oql",
        "name": "channel",
        "type": "text",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {
          "min": null,
          "max": null,
          "pattern": ""
        }
      },
      {
        "system": false,
        "id": "ilmgpujv",
        "name": "type",
        "type": "select",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {
          "maxSelect": 1,
          "values": [
            "TEMPORARY",
            "PERMANENT"
          ]
        }
      },
      {
        "system": false,
        "id": "adyawrvt",
        "name": "owner",
        "type": "text",
        "required": false,
        "presentable": false,
        "unique": false,
        "options": {
          "min": null,
          "max": null,
          "pattern": ""
        }
      }
    ],
    "indexes": [
      "CREATE UNIQUE INDEX `idx_okMYUxg` ON `vcmaker` (`channel`)"
    ],
    "listRule": null,
    "viewRule": null,
    "createRule": null,
    "updateRule": null,
    "deleteRule": null,
    "options": {}
  });

  return Dao(db).saveCollection(collection);
}, (db) => {
  const dao = new Dao(db);
  const collection = dao.findCollectionByNameOrId("yq5t5fajqdx343u");

  return dao.deleteCollection(collection);
})
